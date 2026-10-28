"""Endpunkte rund um Projekte und deren Live-Status."""
from uuid import UUID

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import AuthContext, get_auth_context, require_manager
from app.db import get_pool
from app.schemas import MaterialCostRead, ProjectCreate, ProjectEntries, ProjectRead, ProjectStatusRead, WorkHourRead
from app.services.costing import calculate_cost_summary

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    ctx: AuthContext = Depends(require_manager),
    pool: asyncpg.Pool = Depends(get_pool),
) -> ProjectRead:
    try:
        row = await pool.fetchrow(
            """
            insert into public.projects
                (company_id, projekt_name, budget_netto, status, start_datum, created_by)
            values ($1, $2, $3, $4, $5, $6)
            returning id, projekt_name, budget_netto, status::text as status,
                      start_datum, created_at
            """,
            ctx.company_id,  # aus dem Token, nie aus dem Body
            payload.projekt_name,
            payload.budget_netto,
            payload.status.value,
            payload.start_datum,
            ctx.user_id,
        )
    except asyncpg.UniqueViolationError:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Ein Projekt mit diesem Namen existiert bereits."
        )
    return ProjectRead.model_validate(dict(row))


@router.get("/{projekt_id}/status", response_model=ProjectStatusRead)
async def get_project_status(
    projekt_id: UUID,
    ctx: AuthContext = Depends(get_auth_context),
    pool: asyncpg.Pool = Depends(get_pool),
) -> ProjectStatusRead:
    # Zwei getrennte Subselects statt JOIN beider Tabellen: Ein JOIN würde
    # die Zeilen multiplizieren (Material x Stunden) und die Summen verfälschen.
    row = await pool.fetchrow(
        """
        select
            p.id,
            p.projekt_name,
            p.budget_netto,
            coalesce((select sum(m.betrag_netto)
                        from public.material_costs m
                       where m.projekt_id = p.id and m.company_id = p.company_id), 0) as material_kosten,
            coalesce((select sum(w.stunden_anzahl * w.stundensatz_intern)
                        from public.work_hours w
                       where w.projekt_id = p.id and w.company_id = p.company_id), 0) as lohnkosten
        from public.projects p
        where p.id = $1 and p.company_id = $2
        """,
        projekt_id,
        ctx.company_id,
    )
    if row is None:
        # 404 auch bei fremder Firma -> verrät nicht, ob die ID existiert
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projekt nicht gefunden.")

    summary = calculate_cost_summary(row["budget_netto"], row["material_kosten"], row["lohnkosten"])
    return ProjectStatusRead(
        projekt_id=row["id"],
        projekt_name=row["projekt_name"],
        budget_netto=summary.budget_netto,
        material_kosten=summary.material_kosten,
        lohnkosten=summary.lohnkosten,
        gesamtkosten=summary.gesamtkosten,
        restbudget=summary.restbudget,
        budget_verbrauch_prozent=summary.budget_verbrauch_prozent,
        status_ampel=summary.status_ampel,
    )


@router.get("", response_model=list[ProjectStatusRead])
async def list_projects(
    ctx: AuthContext = Depends(get_auth_context),
    pool: asyncpg.Pool = Depends(get_pool),
) -> list[ProjectStatusRead]:
    # Material und Lohn werden VOR dem Join je Projekt aggregiert -> keine Zeilenvervielfachung.
    rows = await pool.fetch(
        """
        select p.id, p.projekt_name, p.budget_netto,
               coalesce(m.summe, 0) as material_kosten,
               coalesce(w.summe, 0) as lohnkosten
          from public.projects p
          left join (select projekt_id, sum(betrag_netto) as summe
                       from public.material_costs where company_id = $1
                      group by projekt_id) m on m.projekt_id = p.id
          left join (select projekt_id, sum(stunden_anzahl * stundensatz_intern) as summe
                       from public.work_hours where company_id = $1
                      group by projekt_id) w on w.projekt_id = p.id
         where p.company_id = $1 and p.status <> 'archiviert'
         order by p.created_at desc
        """,
        ctx.company_id,
    )
    result: list[ProjectStatusRead] = []
    for r in rows:
        s = calculate_cost_summary(r["budget_netto"], r["material_kosten"], r["lohnkosten"])
        result.append(ProjectStatusRead(
            projekt_id=r["id"], projekt_name=r["projekt_name"],
            budget_netto=s.budget_netto, material_kosten=s.material_kosten,
            lohnkosten=s.lohnkosten, gesamtkosten=s.gesamtkosten,
            restbudget=s.restbudget, budget_verbrauch_prozent=s.budget_verbrauch_prozent,
            status_ampel=s.status_ampel,
        ))
    return result


@router.get("/{projekt_id}/entries", response_model=ProjectEntries)
async def list_project_entries(
    projekt_id: UUID,
    ctx: AuthContext = Depends(get_auth_context),
    pool: asyncpg.Pool = Depends(get_pool),
) -> ProjectEntries:
    exists = await pool.fetchval(
        "select 1 from public.projects where id = $1 and company_id = $2", projekt_id, ctx.company_id
    )
    if not exists:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projekt nicht gefunden.")
    material = await pool.fetch(
        """select id, projekt_id, rechnungs_datum, grosshaendler, betrag_netto, created_at
             from public.material_costs where projekt_id = $1 and company_id = $2
            order by rechnungs_datum desc, created_at desc limit 500""",
        projekt_id, ctx.company_id,
    )
    hours = await pool.fetch(
        """select id, projekt_id, datum, mitarbeiter_name, stunden_anzahl, stundensatz_intern, created_at
             from public.work_hours where projekt_id = $1 and company_id = $2
            order by datum desc, created_at desc limit 500""",
        projekt_id, ctx.company_id,
    )
    return ProjectEntries(
        material=[MaterialCostRead.model_validate(dict(r)) for r in material],
        hours=[WorkHourRead.model_validate(dict(r)) for r in hours],
    )
