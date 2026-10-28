"""Einstiegspunkt. Start: uvicorn app.main:app --reload  (im Ordner backend/)"""
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import create_pool
from app.routers import material_costs, projects, team, work_hours


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Pool einmal beim Start erzeugen, beim Beenden sauber schließen
    app.state.pool = await create_pool(get_settings().database_url)
    try:
        yield
    finally:
        await app.state.pool.close()


app = FastAPI(title="Job-Costing API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,  # explizite Whitelist, kein "*"
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(projects.router)
app.include_router(work_hours.router)
app.include_router(material_costs.router)
app.include_router(team.router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
