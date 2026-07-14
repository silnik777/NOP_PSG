"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..config import settings
from ..infrastructure.persistence.database import init_db
from .v1 import (
    devices,
    emissions,
    export,
    finance,
    gas,
    gas_engine,
    hydraulics,
    mcda,
    prices,
    projects,
    storage,
    thermo,
)

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if settings.auto_create_schema:
        # Dev convenience; production uses `alembic upgrade head`.
        init_db()
    yield


app = FastAPI(
    title=settings.app_title,
    version="1.0.0",
    summary="Validated core: GasPropertyEngine (GERG-2008), Module I compression, "
    "project/variant data model.",
    lifespan=lifespan,
)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "engineVersion": gas_engine._engine.engine_version}


app.include_router(gas_engine.router)
app.include_router(gas.router)
app.include_router(thermo.router)
app.include_router(hydraulics.router)
app.include_router(devices.router)
app.include_router(storage.router)
app.include_router(prices.router)
app.include_router(finance.router)
app.include_router(emissions.router)
app.include_router(mcda.router)
app.include_router(export.router)
app.include_router(projects.router)
