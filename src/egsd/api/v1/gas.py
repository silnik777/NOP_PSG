"""Gas composition endpoints: blending and quality/conditioning."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...application.blending_service import BlendComponent, blend
from ...application.quality_service import QualityLimits, assess
from ...domain.gas.composition import CompositionError
from ...infrastructure.gas_engine.cache import CachingGasEngine
from ...infrastructure.gas_engine.iso6976 import combustion_properties
from ...infrastructure.persistence.database import get_session
from .common import resolve_composition
from .schemas import (
    BlendRequest,
    BlendResponse,
    ConditioningProposalDTO,
    QualityRequest,
    QualityResponse,
    Quantity,
)

router = APIRouter(prefix="/api/v1/gas", tags=["gas"])

_engine = CachingGasEngine()


@router.post("/blend", response_model=BlendResponse)
def blend_streams(req: BlendRequest, session: Session = Depends(get_session)) -> BlendResponse:
    try:
        components = [
            BlendComponent(
                resolve_composition(s.compositionId, s.gasComposition, session), s.share
            )
            for s in req.streams
        ]
        mixture = blend(components)
        cb = combustion_properties(mixture, req.referencePair)
    except (CompositionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    normal_density = _engine.point_properties(mixture, 0.101325, 273.15).state.density_kg_m3
    return BlendResponse(
        composition={k: round(v, 6) for k, v in mixture.fractions.items()},
        grossCalorificValue=Quantity(value=cb.gross_calorific_value_mj_m3, unit="MJ/m3"),
        wobbeIndex=Quantity(value=cb.wobbe_index_mj_m3, unit="MJ/m3"),
        relativeDensity=cb.relative_density,
        normalDensity=Quantity(value=normal_density, unit="kg/m3"),
    )


@router.post("/quality-check", response_model=QualityResponse)
def quality_check(req: QualityRequest, session: Session = Depends(get_session)) -> QualityResponse:
    try:
        composition = resolve_composition(req.compositionId, req.gasComposition, session)
    except CompositionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    limits = None
    if req.limits is not None:
        limits = QualityLimits(
            wobbe_min_mj_m3=req.limits.wobbeMin,
            wobbe_max_mj_m3=req.limits.wobbeMax,
            gross_cv_min_mj_m3=req.limits.grossCvMin,
            reference_pair=req.limits.referencePair,
        )
    result = assess(composition, limits)

    proposal = None
    if result.proposal is not None:
        p = result.proposal
        proposal = ConditioningProposalDTO(
            action=p.action,
            additive=p.additive,
            additiveFractionMol=p.additive_fraction_mol,
            resultingWobbe=Quantity(value=p.resulting_wobbe_mj_m3, unit="MJ/m3"),
            resultingGrossCv=Quantity(value=p.resulting_gross_cv_mj_m3, unit="MJ/m3"),
            note=p.note,
        )
    return QualityResponse(
        withinSpec=result.within_spec,
        wobbeIndex=Quantity(value=result.wobbe_mj_m3, unit="MJ/m3"),
        grossCalorificValue=Quantity(value=result.gross_cv_mj_m3, unit="MJ/m3"),
        relativeDensity=result.relative_density,
        violations=result.violations,
        proposal=proposal,
    )
