"""Authentifizierung & Mandantenzuordnung.

Sicherheitskonzept:
- Das Backend verbindet sich mit der DB als privilegierte Rolle (umgeht RLS).
  Deshalb darf die company_id NIEMALS aus dem Request-Body kommen, sondern
  ausschließlich aus dem verifizierten Token + users-Tabelle.
- Jede Query filtert explizit nach ctx.company_id.
"""
from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

import asyncpg
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.config import get_settings
from app.db import get_pool

_bearer = HTTPBearer(auto_error=False)
MANAGER_ROLES = frozenset({"owner", "admin"})


@dataclass(frozen=True, slots=True)
class AuthContext:
    user_id: UUID
    company_id: UUID
    role: str


@lru_cache
def _jwks_client(supabase_url: str) -> PyJWKClient:
    return PyJWKClient(f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json", cache_keys=True)


def _decode_token(token: str) -> dict:
    """Prüft Signatur, Ablauf und Audience des Supabase-JWT (synchron)."""
    settings = get_settings()
    if settings.supabase_jwt_secret:
        return jwt.decode(
            token, settings.supabase_jwt_secret, algorithms=["HS256"], audience="authenticated"
        )
    assert settings.supabase_url  # durch Settings-Validator garantiert
    key = _jwks_client(settings.supabase_url).get_signing_key_from_jwt(token).key
    return jwt.decode(token, key, algorithms=["ES256", "RS256"], audience="authenticated")


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Ungültiges oder fehlendes Token.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_auth_context(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    pool: asyncpg.Pool = Depends(get_pool),
) -> AuthContext:
    if creds is None:
        raise _unauthorized()
    try:
        # Ggf. blockierender JWKS-Abruf -> in Threadpool, um den Event-Loop frei zu halten
        claims = await run_in_threadpool(_decode_token, creds.credentials)
        user_id = UUID(claims["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _unauthorized()

    row = await pool.fetchrow(
        "select company_id, role::text as role from public.users where id = $1", user_id
    )
    if row is None:
        # Gültiger Login, aber noch kein Firmenprofil (Onboarding fehlt)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Nutzer ist keiner Firma zugeordnet.")
    return AuthContext(user_id=user_id, company_id=row["company_id"], role=row["role"])


async def require_manager(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
    """Nur Owner/Admin dürfen z. B. Projekte (mit Budget) anlegen."""
    if ctx.role not in MANAGER_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Keine Berechtigung für diese Aktion.")
    return ctx
