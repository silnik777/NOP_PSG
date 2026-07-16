"""Gas composition endpoints: blending and quality/conditioning."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...application.blending_service import BlendComponent, blend
from ...application.quality_service import QualityLimits, assess
from ...domain.gas.composition import CompositionError
from ...infrastructure.gas_engine.cache import CachingGasEngine
from ...infrastructure.gas_engine.iso6976 import combustion_properties
from ...infrastructure.persistence.database import get_session
from ...infrastructure.persistence.models import QualityRequirementSetRow
from .common import resolve_composition
from .schemas import (
    BlendRequest,
    BlendResponse,
    ConditioningProposalDTO,
    QualityRequest,
    QualityRequirementSetDTO,
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


@router.get("/quality-requirement-sets", response_model=list[QualityRequirementSetDTO])
def quality_requirement_sets(
    session: Session = Depends(get_session),
) -> list[QualityRequirementSetDTO]:
    """Catalog of versioned, selectable quality requirement sets (§21, MVP #7)."""
    rows = session.scalars(
        select(QualityRequirementSetRow).order_by(QualityRequirementSetRow.code)
    ).all()
    return [_req_set_dto(r) for r in rows]


def _req_set_dto(r: QualityRequirementSetRow) -> QualityRequirementSetDTO:
    return QualityRequirementSetDTO(
        code=r.code, name=r.name, version=r.version, application=r.application,
        geography=r.geography, referenceDocument=r.reference_document,
        referencePair=r.reference_pair, wobbeMin=r.wobbe_min_mj_m3,
        wobbeMax=r.wobbe_max_mj_m3, grossCvMin=r.gross_cv_min_mj_m3,
        status=r.status, source=r.source,
    )


@router.post("/quality-check", response_model=QualityResponse)
def quality_check(req: QualityRequest, session: Session = Depends(get_session)) -> QualityResponse:
    try:
        composition = resolve_composition(req.compositionId, req.gasComposition, session)
    except CompositionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    limits = None
    set_label = "domyślny grupa E (wbudowany)"
    if req.requirementSetId is not None:
        # Explicit, versioned set from the catalog (takes precedence over raw limits).
        row = session.scalar(
            select(QualityRequirementSetRow).where(
                QualityRequirementSetRow.code == req.requirementSetId
            )
        )
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown quality requirement set: {req.requirementSetId!r}",
            )
        limits = QualityLimits(
            wobbe_min_mj_m3=row.wobbe_min_mj_m3, wobbe_max_mj_m3=row.wobbe_max_mj_m3,
            gross_cv_min_mj_m3=row.gross_cv_min_mj_m3, reference_pair=row.reference_pair,
        )
        set_label = f"{row.code} v{row.version} — {row.name}"
    elif req.limits is not None:
        limits = QualityLimits(
            wobbe_min_mj_m3=req.limits.wobbeMin,
            wobbe_max_mj_m3=req.limits.wobbeMax,
            gross_cv_min_mj_m3=req.limits.grossCvMin,
            reference_pair=req.limits.referencePair,
        )
        set_label = "limity użytkownika (ad hoc)"
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
        requirementSet=set_label,
    )
