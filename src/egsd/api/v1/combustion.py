"""Combustion endpoints: stoichiometric CO2 from fuel composition (§27), and a
before/after comparison for conditioning additions such as propane (EMI-CMB-011)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...application.combustion_service import evaluate
from ...domain.combustion.models import CombustionInput
from ...domain.gas.composition import CompositionError
from ...infrastructure.persistence.database import get_session
from .common import resolve_composition

router = APIRouter(prefix="/api/v1/combustion", tags=["combustion"])


class CombustionOptions(BaseModel):
    excessAirRatio: float | None = Field(None, description="lambda = actual air / stoich air")
    flueO2DryPct: float | None = Field(None, description="target O2 in dry flue gas, vol %")
    carbonOxidationFactor: float = 1.0
    biogenicFraction: dict[str, float] = Field(default_factory=dict)
    usefulEfficiency: float | None = None
    referencePair: str = "25/0"


class CombustionEmissionRequest(BaseModel):
    compositionId: str | None = None
    gasComposition: dict[str, float] | None = None
    options: CombustionOptions = Field(default_factory=CombustionOptions)


class CombustionEmissionResponse(BaseModel):
    method: str
    theoreticalO2MolPerMol: float
    theoreticalAirMolPerMol: float
    excessAirRatio: float
    co2TotalMolPerMol: float
    co2FossilMolPerMol: float
    co2BiogenicMolPerMol: float
    flueGasWet: dict[str, float]
    flueGasDry: dict[str, float]
    co2KgPerNm3Fuel: float
    co2KgPerGjInput: float
    co2KgPerGjUseful: float | None
    grossCalorificValueMjM3: float
    resultClass: str
    warnings: list[str]


def _to_input(o: CombustionOptions) -> CombustionInput:
    return CombustionInput(
        excess_air_ratio=o.excessAirRatio,
        flue_o2_dry_pct=o.flueO2DryPct,
        carbon_oxidation_factor=o.carbonOxidationFactor,
        biogenic_fraction=o.biogenicFraction,
        useful_efficiency=o.usefulEfficiency,
        reference_pair=o.referencePair,
    )


def _to_response(r) -> CombustionEmissionResponse:
    return CombustionEmissionResponse(
        method=r.method.value,
        theoreticalO2MolPerMol=round(r.theoretical_o2_mol_per_mol, 6),
        theoreticalAirMolPerMol=round(r.theoretical_air_mol_per_mol, 6),
        excessAirRatio=round(r.excess_air_ratio, 6),
        co2TotalMolPerMol=round(r.co2_total_mol_per_mol, 6),
        co2FossilMolPerMol=round(r.co2_fossil_mol_per_mol, 6),
        co2BiogenicMolPerMol=round(r.co2_biogenic_mol_per_mol, 6),
        flueGasWet={k: round(v, 6) for k, v in r.flue_gas.wet.items()},
        flueGasDry={k: round(v, 6) for k, v in r.flue_gas.dry.items()},
        co2KgPerNm3Fuel=round(r.co2_kg_per_nm3_fuel, 6),
        co2KgPerGjInput=round(r.co2_kg_per_gj_input, 4),
        co2KgPerGjUseful=(
            round(r.co2_kg_per_gj_useful, 4) if r.co2_kg_per_gj_useful is not None else None
        ),
        grossCalorificValueMjM3=round(r.gross_calorific_value_mj_m3, 4),
        resultClass=r.result_class,
        warnings=list(r.warnings),
    )


@router.post("/emissions", response_model=CombustionEmissionResponse)
def combustion_emissions(
    req: CombustionEmissionRequest, session: Session = Depends(get_session)
) -> CombustionEmissionResponse:
    try:
        comp = resolve_composition(req.compositionId, req.gasComposition, session)
        return _to_response(evaluate(comp, _to_input(req.options)))
    except (CompositionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


class CompareRequest(BaseModel):
    baseCompositionId: str | None = None
    baseGasComposition: dict[str, float] | None = None
    # The gas after conditioning/blending (e.g. after propane enrichment).
    modifiedCompositionId: str | None = None
    modifiedGasComposition: dict[str, float] | None = None
    options: CombustionOptions = Field(default_factory=CombustionOptions)


class CompareResponse(BaseModel):
    base: CombustionEmissionResponse
    modified: CombustionEmissionResponse
    deltaCo2KgPerGjInput: float
    deltaCo2KgPerNm3Fuel: float


@router.post("/compare", response_model=CompareResponse)
def combustion_compare(
    req: CompareRequest, session: Session = Depends(get_session)
) -> CompareResponse:
    """EMI-CMB-011 — compare combustion CO2 before and after adding propane, hydrogen,
    biomethane or another component. Each side is an independent, method-tagged run."""
    try:
        base_comp = resolve_composition(req.baseCompositionId, req.baseGasComposition, session)
        mod_comp = resolve_composition(
            req.modifiedCompositionId, req.modifiedGasComposition, session
        )
        opts = _to_input(req.options)
        base = evaluate(base_comp, opts)
        mod = evaluate(mod_comp, opts)
    except (CompositionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return CompareResponse(
        base=_to_response(base),
        modified=_to_response(mod),
        deltaCo2KgPerGjInput=round(mod.co2_kg_per_gj_input - base.co2_kg_per_gj_input, 4),
        deltaCo2KgPerNm3Fuel=round(mod.co2_kg_per_nm3_fuel - base.co2_kg_per_nm3_fuel, 6),
    )
