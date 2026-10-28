"""Zentrale Konfiguration.

Warum pydantic-settings? Alle Umgebungsvariablen werden beim Start einmalig
typisiert validiert -> die App crasht sofort bei Fehlkonfiguration, statt
erst zur Laufzeit bei der ersten Anfrage.
"""
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    supabase_jwt_secret: str | None = None  # HS256 (klassisch)
    supabase_url: str | None = None         # JWKS (asymmetrische Signing Keys)
    supabase_service_role_key: str | None = None  # NUR Backend! Für Einladungen
    frontend_url: str = "http://localhost:3000"
    gemini_daily_scan_limit: int = 100  # Beleg-Scans pro Firma und Tag (pro Prozess)
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"  # per Env überschreibbar
    cors_origins: list[str] = ["http://localhost:3000"]

    @model_validator(mode="after")
    def _require_jwt_verification_source(self) -> "Settings":
        if not (self.supabase_jwt_secret or self.supabase_url):
            raise ValueError("SUPABASE_JWT_SECRET oder SUPABASE_URL muss gesetzt sein.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
