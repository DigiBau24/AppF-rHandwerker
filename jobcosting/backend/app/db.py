"""Datenbankzugriff über einen asyncpg-Connection-Pool.

Warum asyncpg statt ORM? Für Aggregationen (Summen über Material/Stunden)
ist handgeschriebenes SQL transparenter, schneller und leichter zu auditieren.
Alle Queries sind parametrisiert ($1, $2 ...) -> kein SQL-Injection-Risiko.
"""
import asyncpg
from fastapi import Request


async def create_pool(dsn: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(
        dsn=dsn,
        min_size=1,
        max_size=10,
        command_timeout=15,
        # Nötig, falls du den Supabase-Pooler im Transaction-Mode (Port 6543) nutzt;
        # bei direkter Verbindung schadet es nicht.
        statement_cache_size=0,
    )


def get_pool(request: Request) -> asyncpg.Pool:
    """FastAPI-Dependency: liefert den beim Start erzeugten Pool."""
    return request.app.state.pool
