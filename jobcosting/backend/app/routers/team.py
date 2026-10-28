"""Profil (/me) und Team-Verwaltung inkl. Einladung per E-Mail.

Einladung: Das Backend ruft die Supabase-Admin-API (service_role, NUR serverseitig) auf. Supabase legt
den Auth-Nutzer sofort an und verschickt den Link; wir legen direkt die passende public.users-Zeile
mit Firma + Rolle an. Dadurch ist der Eingeladene beim ersten Login bereits seiner Firma zugeordnet.
"""
from uuid import UUID

import asyncpg
import httpx
from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import AuthContext, get_auth_context, require_manager
from app.config import get_settings
from app.db import get_pool
from app.schemas import InviteCreate, MeRead, TeamMember

router = APIRouter(prefix="/api/v1", tags=["team"])


def _admin_headers(key: str) -> dict[str, str]:
    headers = {"apikey": key, "Content-Type": "application/json"}
    if key.startswith("eyJ"):  # klassischer JWT-service_role-Key; neue sb_secret_-Keys nur als apikey
        headers["Authorization"] = f"Bearer {key}"
    return headers


@router.get("/me", response_model=MeRead)
async def me(ctx: AuthContext = Depends(get_auth_context), pool: asyncpg.Pool = Depends(get_pool)) -> MeRead:
    name = await pool.fetchval("select name from public.companies where id = $1", ctx.company_id)
    return MeRead(user_id=ctx.user_id, company_id=ctx.company_id, company_name=name, role=ctx.role)


@router.get("/team", response_model=list[TeamMember])
async def list_team(ctx: AuthContext = Depends(require_manager), pool: asyncpg.Pool = Depends(get_pool)) -> list[TeamMember]:
    rows = await pool.fetch(
        "select id, email, full_name, role::text as role from public.users where company_id = $1 order by created_at",
        ctx.company_id,
    )
    return [TeamMember.model_validate(dict(r)) for r in rows]


@router.post("/team/invitations", response_model=TeamMember, status_code=status.HTTP_201_CREATED)
async def invite_member(
    payload: InviteCreate,
    ctx: AuthContext = Depends(require_manager),
    pool: asyncpg.Pool = Depends(get_pool),
) -> TeamMember:
    if payload.role == "admin" and ctx.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Nur der Inhaber darf Admins einladen.")
    s = get_settings()
    if not (s.supabase_url and s.supabase_service_role_key):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Einladungen sind nicht konfiguriert.")
    base = s.supabase_url.rstrip("/")
    headers = _admin_headers(s.supabase_service_role_key)

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{base}/auth/v1/invite", params={"redirect_to": s.frontend_url}, headers=headers,
                json={"email": payload.email, "data": {"full_name": payload.full_name}},
            )
    except httpx.HTTPError:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Einladung konnte nicht versendet werden.") from None
    if resp.status_code in (400, 409, 422):
        raise HTTPException(status.HTTP_409_CONFLICT, "Diese E-Mail-Adresse ist bereits registriert oder ungültig.")
    if not resp.is_success:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Einladung konnte nicht versendet werden.")
    auth_user_id = UUID(resp.json()["id"])

    try:
        await pool.execute(
            "insert into public.users (id, company_id, email, full_name, role) values ($1, $2, $3, $4, $5::public.user_role)",
            auth_user_id, ctx.company_id, str(payload.email), payload.full_name, payload.role,
        )
    except asyncpg.PostgresError:
        # Aufräumen, damit kein verwaister Auth-Nutzer ohne Firma zurückbleibt
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                await client.delete(f"{base}/auth/v1/admin/users/{auth_user_id}", headers=headers)
        except httpx.HTTPError:
            pass
        raise HTTPException(status.HTTP_409_CONFLICT, "Nutzer konnte keiner Firma zugeordnet werden.") from None
    return TeamMember(id=auth_user_id, email=str(payload.email), full_name=payload.full_name, role=payload.role)
