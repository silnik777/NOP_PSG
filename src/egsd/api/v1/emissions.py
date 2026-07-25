"""Emission endpoints: Scope 1/2/3 CO2e footprint (CoreEmissionEngine)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...application.emission_service import evaluate
from ...domain.emissions.models import EmissionFactors, EmissionInput

router = APIRouter(prefix="/api/v1/emissions", tags=["emissions"])


class EmissionFactorsDTO(BaseModel):
    gridElectricityKgCo2PerMwh: float = 597.0
    gasCombustionKgCo2PerGj: float = 55.82
    h2GrayKgCo2ePerKg: float = 10.9
    h2GreenKgCo2ePerKg: float = 0.5


class FootprintRequest(BaseModel):
    methaneLeakTonnes: float = 0.0
    hydrogenLeakTonnes: float = 0.0
    heaterGasUseGj: float = 0.0
    gridElectricityMwh: float = 0.0
    hydrogenSuppliedTonnes: float = 0.0
    hydrogenOrigin: str = "gray"
    factors: EmissionFactorsDTO | None = None


class FootprintResponse(BaseModel):
    scope1TCo2e: float
    scope2TCo2e: float
    scope3TCo2e: float
    totalTCo2e: float
    detail: dict[str, float]
    gwpSource: str
    factorsVintage: str


@router.post("/footprint", response_model=FootprintResponse)
def footprint(req: FootprintRequest) -> FootprintResponse:
    factors = None
    if req.factors is not None:
        factors = EmissionFactors(
            grid_electricity_kg_co2_per_mwh=req.factors.gridElectricityKgCo2PerMwh,
            gas_combustion_kg_co2_per_gj=req.factors.gasCombustionKgCo2PerGj,
            h2_gray_kg_co2e_per_kg=req.factors.h2GrayKgCo2ePerKg,
            h2_green_kg_co2e_per_kg=req.factors.h2GreenKgCo2ePerKg,
            vintage="custom (user override — SION amber)",
        )
    try:
        result = evaluate(
            EmissionInput(
                methane_leak_tonnes=req.methaneLeakTonnes,
                hydrogen_leak_tonnes=req.hydrogenLeakTonnes,
                heater_gas_use_gj=req.heaterGasUseGj,
                grid_electricity_mwh=req.gridElectricityMwh,
                hydrogen_supplied_tonnes=req.hydrogenSuppliedTonnes,
                hydrogen_origin=req.hydrogenOrigin,
            ),
            factors,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    b = result.breakdown
    return FootprintResponse(
        scope1TCo2e=b.scope1_t_co2e, scope2TCo2e=b.scope2_t_co2e, scope3TCo2e=b.scope3_t_co2e,
        totalTCo2e=b.total_t_co2e, detail=result.detail,
        gwpSource=result.gwp_source, factorsVintage=result.factors_vintage,
    )
