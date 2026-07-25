"""MCDA endpoints: TOPSIS ranking with the comparability Gatekeeper."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...application.mcda_service import rank
from ...domain.mcda.models import (
    GatekeeperError,
    MacroAssumptions,
    VariantScore,
    Weights,
)

router = APIRouter(prefix="/api/v1/mcda", tags=["mcda"])


class AssumptionsDTO(BaseModel):
    discountRate: float
    scenarioCode: str
    engineVersion: str


class VariantScoreDTO(BaseModel):
    name: str
    npv: float
    capex: float
    co2eTonnes: float
    trl: float
    assumptions: AssumptionsDTO | None = None


class WeightsDTO(BaseModel):
    npv: float = 0.4
    capex: float = 0.2
    co2e: float = 0.25
    trl: float = 0.15


class RankRequest(BaseModel):
    variants: list[VariantScoreDTO]
    weights: WeightsDTO | None = None


class RankedVariantDTO(BaseModel):
    name: str
    closeness: float
    rank: int


class RankResponse(BaseModel):
    method: str
    ranking: list[RankedVariantDTO]
    weightsApplied: WeightsDTO
    consistency: str


@router.post("/rank", response_model=RankResponse)
def rank_variants(req: RankRequest) -> RankResponse:
    variants = [
        VariantScore(
            name=v.name, npv=v.npv, capex=v.capex, co2e_tonnes=v.co2eTonnes, trl=v.trl,
            assumptions=(
                MacroAssumptions(
                    discount_rate=v.assumptions.discountRate,
                    scenario_code=v.assumptions.scenarioCode,
                    engine_version=v.assumptions.engineVersion,
                )
                if v.assumptions
                else None
            ),
        )
        for v in req.variants
    ]
    weights = (
        Weights(npv=req.weights.npv, capex=req.weights.capex,
                co2e=req.weights.co2e, trl=req.weights.trl)
        if req.weights
        else None
    )
    try:
        result = rank(variants, weights)
    except GatekeeperError as exc:
        # W7.2 — explicit blocking message listing every discrepancy.
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    w = result.weights
    return RankResponse(
        method=result.method,
        ranking=[
            RankedVariantDTO(name=r.name, closeness=r.closeness, rank=r.rank)
            for r in result.ranking
        ],
        weightsApplied=WeightsDTO(npv=w.npv, capex=w.capex, co2e=w.co2e, trl=w.trl),
        consistency=result.consistency,
    )
