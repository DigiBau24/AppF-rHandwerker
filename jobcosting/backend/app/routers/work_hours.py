"""Endpunkte für Arbeitszeitbuchungen."""
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from uuid import UUID

from app.auth import MANAGER_ROLES, AuthContext, get_auth_context
from app.db import get_pool
from app.schemas import WorkHourCreate, WorkHourRead, WorkHourUpdate

router = APIRouter(prefix="/api/v1/work-hours", tags=["work-hours"])


@router.post("", response_model=WorkHourRead, status_code=status.HTTP_201_CREATED)
async def book_work_hours(
    payload: WorkHourCreate,
    ctx: AuthContext = Depends(get_auth_context),
    pool: asyncpg.Pool = Depends(get_pool),
) -> WorkHourRead:
    async with pool.acquire() as conn:
        async with conn.transaction():
            # FOR SHARE sperrt die Projektzeile gegen gleichzeitiges Archivieren,
            # bis die Buchung committed ist. Zusätzlich prüft die Query den Mandanten.
            project = await conn.fetchrow(
                """
                select status::text as status
                  from public.projects
                 where id = $1 and company_id = $2
                   for share
                """,
                payload.projekt_id,
                ctx.company_id,
            )
            if project is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Projekt nicht gefunden.")
            if project["status"] == "archiviert":
                raise HTTPException(
                    status.HTTP_409_CONFLICT, "Auf archivierte Projekte kann nicht gebucht werden."
                )

            row = await conn.fetchrow(
                """
                insert into public.work_hours
                    (company_id, projekt_id, datum, mitarbeiter_name,
                     stunden_anzahl, stundensatz_intern, created_by)
                values ($1, $2, $3, $4, $5, $6, $7)
                returning id, projekt_id, datum, mitarbeiter_name,
                          stunden_anzahl, stundensatz_intern, created_at
                """,
                ctx.company_id,
                payload.projekt_id,
                payload.datum,
                payload.mitarbeiter_name,
                payload.stunden_anzahl,
                payload.stundensatz_intern,
                ctx.user_id,
            )
    return WorkHourRead.model_validate(dict(row))


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work_hours(
    entry_id: UUID,
    ctx: AuthContext = Depends(get_auth_context),
    pool: asyncpg.Pool = Depends(get_pool),
) -> None:
    deleted = await pool.fetchval(
        """delete from public.work_hours
            where id = $1 and company_id = $2 and ($3::boolean or created_by = $4)
        returning id""",
        entry_id, ctx.company_id, ctx.role in MANAGER_ROLES, ctx.user_id,
    )
    if deleted is None:  # nicht vorhanden ODER keine Berechtigung -> gleiche Antwort
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Buchung nicht gefunden.")


@router.patch("/{entry_id}", response_model=WorkHourRead)
async def update_work_hours(
    entry_id: UUID,
    payload: WorkHourUpdate,
    ctx: AuthContext = Depends(get_auth_context),
    pool: asyncpg.Pool = Depends(get_pool),
) -> WorkHourRead:
    # coalesce: nicht gesendete Felder (None) bleiben unverändert. Gleiche Rechteregel wie DELETE;
    # archivierte Projekte sind schreibgeschützt.
    row = await pool.fetchrow(
        """
        update public.work_hours w set
            datum              = coalesce($3, w.datum),
            mitarbeiter_name   = coalesce($4, w.mitarbeiter_name),
            stunden_anzahl     = coalesce($5, w.stunden_anzahl),
            stundensatz_intern = coalesce($6, w.stundensatz_intern)
         where w.id = $1 and w.company_id = $2 and ($7::boolean or w.created_by = $8)
           and exists (select 1 from public.projects p
                        where p.id = w.projekt_id and p.company_id = w.company_id and p.status <> 'archiviert')
        returning w.id, w.projekt_id, w.datum, w.mitarbeiter_name, w.stunden_anzahl, w.stundensatz_intern, w.created_at
        """,
        entry_id, ctx.company_id, payload.datum, payload.mitarbeiter_name, payload.stunden_anzahl,
        payload.stundensatz_intern, ctx.role in MANAGER_ROLES, ctx.user_id,
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Buchung nicht gefunden.")
    return WorkHourRead.model_validate(dict(row))
