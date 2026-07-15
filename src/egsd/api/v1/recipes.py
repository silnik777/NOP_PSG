"""Own gas profiles and versioned blend recipes (OPZ §20, MVP #1 and #5).

Profiles and recipes are persistent, versioned objects. A recipe re-run resolves its streams
and produces a deterministic blend, fingerprinted by a config checksum for reproducibility.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...application.blending_service import BlendComponent, blend
from ...domain.gas.composition import CompositionError
from ...domain.project.hashing import result_hash
from ...infrastructure.gas_engine.cache import CachingGasEngine
from ...infrastructure.gas_engine.iso6976 import combustion_properties
from ...infrastructure.persistence.database import get_session
from ...infrastructure.persistence.profile_recipe_repository import (
    latest_recipe,
    list_profiles,
    list_recipes,
    save_profile,
    save_recipe,
)
from .common import resolve_composition
from .schemas import Quantity

router = APIRouter(prefix="/api/v1/gas", tags=["profiles-recipes"])

_engine = CachingGasEngine()


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return (s or "profil")[:60]


# ----- Composition profiles (MVP #1) ------------------------------------------


class ProfileIn(BaseModel):
    name: str
    gasComposition: dict[str, float]
    code: str | None = None
    status: str = "draft"
    owner: str = "system"
    source: str = ""


class ProfileOut(BaseModel):
    code: str
    name: str
    version: int
    status: str
    owner: str
    source: str
    fractions: dict[str, float]


@router.post("/profiles", response_model=ProfileOut, status_code=201)
def create_profile(body: ProfileIn, session: Session = Depends(get_session)) -> ProfileOut:
    try:
        # Normalize/validate via the domain value object before persisting.
        comp = resolve_composition(None, body.gasComposition, session)
    except CompositionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    code = body.code or _slug(body.name)
    row = save_profile(
        session, code=code, name=body.name, fractions=comp.fractions,
        status=body.status, owner=body.owner, source=body.source,
    )
    session.commit()
    return _profile_out(row)


@router.get("/profiles", response_model=list[ProfileOut])
def get_profiles(session: Session = Depends(get_session)) -> list[ProfileOut]:
    return [_profile_out(r) for r in list_profiles(session)]


def _profile_out(row) -> ProfileOut:
    return ProfileOut(
        code=row.code, name=row.name, version=row.version, status=row.status,
        owner=row.owner, source=row.source, fractions=row.fractions,
    )


# ----- Blend recipes (MVP #5) -------------------------------------------------


class RecipeStreamDTO(BaseModel):
    compositionId: str | None = None
    gasComposition: dict[str, float] | None = None
    share: float = Field(gt=0)


class RecipeIn(BaseModel):
    name: str
    streams: list[RecipeStreamDTO]
    code: str | None = None
    referencePair: str = "25/0"
    status: str = "draft"
    owner: str = "system"


class RecipeOut(BaseModel):
    code: str
    name: str
    version: int
    status: str
    owner: str
    streams: list[dict]
    referencePair: str
    configChecksum: str


def _recipe_checksum(streams: list[dict], reference_pair: str) -> str:
    return result_hash(
        {"streams": streams, "referencePair": reference_pair}, {"blend": "1.0.0"}
    )


@router.post("/recipes", response_model=RecipeOut, status_code=201)
def create_recipe(body: RecipeIn, session: Session = Depends(get_session)) -> RecipeOut:
    if not body.streams:
        raise HTTPException(status_code=422, detail="A recipe needs at least one stream.")
    streams = [
        {"compositionId": s.compositionId, "gasComposition": s.gasComposition, "share": s.share}
        for s in body.streams
    ]
    # Validate now so a saved recipe is always runnable.
    try:
        for s in body.streams:
            resolve_composition(s.compositionId, s.gasComposition, session)
    except CompositionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    code = body.code or _slug(body.name)
    checksum = _recipe_checksum(streams, body.referencePair)
    row = save_recipe(
        session, code=code, name=body.name, streams=streams,
        reference_pair=body.referencePair, config_checksum=checksum,
        status=body.status, owner=body.owner,
    )
    session.commit()
    return _recipe_out(row)


@router.get("/recipes", response_model=list[RecipeOut])
def get_recipes(session: Session = Depends(get_session)) -> list[RecipeOut]:
    return [_recipe_out(r) for r in list_recipes(session)]


class RecipeRunResponse(BaseModel):
    code: str
    version: int
    configChecksum: str
    composition: dict[str, float]
    grossCalorificValue: Quantity
    wobbeIndex: Quantity
    relativeDensity: float


@router.post("/recipes/{code}/run", response_model=RecipeRunResponse)
def run_recipe(code: str, session: Session = Depends(get_session)) -> RecipeRunResponse:
    """Re-run a saved recipe (function 10, §20.1): resolve streams → blend → deterministic
    result, verified by the stored config checksum."""
    row = latest_recipe(session, code)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown recipe: {code!r}")
    try:
        components = [
            BlendComponent(
                resolve_composition(s.get("compositionId"), s.get("gasComposition"), session),
                s["share"],
            )
            for s in row.streams
        ]
        mixture = blend(components)
        cb = combustion_properties(mixture, row.reference_pair)
    except (CompositionError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RecipeRunResponse(
        code=row.code, version=row.version, configChecksum=row.config_checksum,
        composition={k: round(v, 6) for k, v in mixture.fractions.items()},
        grossCalorificValue=Quantity(value=cb.gross_calorific_value_mj_m3, unit="MJ/m3"),
        wobbeIndex=Quantity(value=cb.wobbe_index_mj_m3, unit="MJ/m3"),
        relativeDensity=cb.relative_density,
    )


def _recipe_out(row) -> RecipeOut:
    return RecipeOut(
        code=row.code, name=row.name, version=row.version, status=row.status,
        owner=row.owner, streams=row.streams, referencePair=row.reference_pair,
        configChecksum=row.config_checksum,
    )
