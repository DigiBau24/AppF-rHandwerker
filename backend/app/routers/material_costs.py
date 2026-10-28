"""Beleg-Import: 1) scan (KI-Vorschlag, schreibt nichts)  2) buchen (nach Prüfung durch den Nutzer)."""
import json
from datetime import date

import asyncpg
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from uuid import UUID

from app.auth import MANAGER_ROLES, AuthContext, get_auth_context
from app.config import get_settings
from app.db import get_pool
from app.schemas import MaterialCostCreate, MaterialCostRead, MaterialCostUpdate, ScanResult
from app.services.gemini import GeminiError, extract_invoice

router = APIRouter(prefix="/api/v1/material-costs", tags=["material-costs"])

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
MAX_BYTES = 8 * 1024 * 1024

# Kostenschutz: Scans pro Firma und Tag begrenzen. In-Memory = gilt pro Prozess;
# bei mehreren Instanzen später auf Redis/DB umstellen.
_scan_usage: dict[tuple[UUID, date], int] = {}


def _check_scan_quota(company_id: UUID) -> None:
    today = date.today()
    for key in [k for k in _scan_usage if k[1] != today]:
        del _scan_usage[key]
    used = _scan_usage.get((company_id, today), 0)
    if used >= get_settings().gemini_daily_scan_limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Tageslimit für Beleg-Scans erreicht. Bitte manuell erfassen.")
    _scan_usage[(company_id, today)] = used + 1


@router.post("/scan", response_model=ScanResult)
async def scan_invoice(file: UploadFile = File(...), ctx: AuthContext = Depends(get_auth_context)) -> ScanResult:
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Erlaubt: JPG, PNG, WebP oder PDF.")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Datei größer als 8 MB.")
    _check_scan_quota(ctx.company_id)
    try:
        extracted, raw = await extract_invoice(data, file.content_type)
    except GeminiError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e))
    return ScanResult(extracted=extracted, raw=raw)


@router.post("", response_model=MaterialCostRead, status_code=status.HTTP_201_CREATED)
async def create_material_cost(
    payload: MaterialCostCreate,
    ctx: AuthContext = Depends(get_auth_context),
    pool: asyncpg.Pool = Depends(get_pool),
) -> MaterialCostRead:
    async with pool.acquire() as conn:
        async with conn.transaction():
            project = await conn.fetchrow(
                "select status::text as status from public.projects where id = $1 and company_id = $2 for share",
                payload.projekt_id, ctx.company_id,
            )
            if project is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Projekt nicht gefunden.")
            if project["status"] == "archiviert":
                raise HTTPException(status.HTTP_409_CONFLICT, "Auf archivierte Projekte kann nicht gebucht werden.")
            row = await conn.fetchrow(
                """
                insert into public.material_costs
                    (company_id, projekt_id, rechnungs_datum, grosshaendler, betrag_netto, gemini_raw_json, created_by)
                values ($1, $2, $3, $4, $5, $6::jsonb, $7)
                returning id, projekt_id, rechnungs_datum, grosshaendler, betrag_netto, created_at
                """,
                ctx.company_id, payload.projekt_id, payload.rechnungs_datum, payload.grosshaendler,
                payload.betrag_netto,
                json.dumps(payload.gemini_raw_json) if payload.gemini_raw_json is not None else None,
                ctx.user_id,
            )
    return MaterialCostRead.model_validate(dict(row))


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material_cost(
    entry_id: UUID,
    ctx: AuthContext = Depends(get_auth_context),
    pool: asyncpg.Pool = Depends(get_pool),
) -> None:
    deleted = await pool.fetchval(
        """delete from public.material_costs
            where id = $1 and company_id = $2 and ($3::boolean or created_by = $4)
        returning id""",
        entry_id, ctx.company_id, ctx.role in MANAGER_ROLES, ctx.user_id,
    )
    if deleted is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Buchung nicht gefunden.")


@router.patch("/{entry_id}", response_model=MaterialCostRead)
async def update_material_cost(
    entry_id: UUID,
    payload: MaterialCostUpdate,
    ctx: AuthContext = Depends(get_auth_context),
    pool: asyncpg.Pool = Depends(get_pool),
) -> MaterialCostRead:
    row = await pool.fetchrow(
        """
        update public.material_costs m set
            rechnungs_datum = coalesce($3, m.rechnungs_datum),
            grosshaendler   = coalesce($4, m.grosshaendler),
            betrag_netto    = coalesce($5, m.betrag_netto)
         where m.id = $1 and m.company_id = $2 and ($6::boolean or m.created_by = $7)
           and exists (select 1 from public.projects p
                        where p.id = m.projekt_id and p.company_id = m.company_id and p.status <> 'archiviert')
        returning m.id, m.projekt_id, m.rechnungs_datum, m.grosshaendler, m.betrag_netto, m.created_at
        """,
        entry_id, ctx.company_id, payload.rechnungs_datum, payload.grosshaendler, payload.betrag_netto,
        ctx.role in MANAGER_ROLES, ctx.user_id,
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Buchung nicht gefunden.")
    return MaterialCostRead.model_validate(dict(row))
