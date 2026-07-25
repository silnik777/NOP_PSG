"""Gas-engine endpoints: point properties (§2.1) and combustion (ISO 6976)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException

from ...domain.gas.composition import CompositionError, GasComposition
from ...infrastructure.gas_engine.cache import CachingGasEngine
from ...infrastructure.gas_engine.errors import OutOfRangeError, StateSolveError
from ...infrastructure.gas_engine.iso6976 import combustion_properties
from ..units import pressure_to_mpa, temperature_to_k
from .schemas import (
    CombustionRequest,
    CombustionResponse,
    PointPropertiesRequest,
    PointPropertiesResponse,
    Quantity,
    ValidationBlock,
)

logger = logging.getLogger("egsd.gas_engine")
router = APIRouter(prefix="/api/v1/gas-engine", tags=["gas-engine"])

# Single cached engine instance (stateless computations, safe to share).
_engine = CachingGasEngine()


@router.post("/point-properties", response_model=PointPropertiesResponse)
def point_properties(req: PointPropertiesRequest) -> PointPropertiesResponse:
    try:
        composition = GasComposition.from_mapping(req.gasComposition)
        p_mpa = pressure_to_mpa(req.stateVariables.pressure.value, req.stateVariables.pressure.unit)
        t_k = temperature_to_k(
            req.stateVariables.temperature.value, req.stateVariables.temperature.unit
        )
    except (CompositionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        result = _engine.point_properties(composition, p_mpa, t_k)
    except OutOfRangeError as exc:
        # W3.4 — log critical event and reject.
        logger.critical("Out-of-range calculation rejected: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except StateSolveError as exc:
        logger.error("State solve failed: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    s = result.state
    return PointPropertiesResponse(
        meta={
            "timestampUtc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "engineVersion": _engine.engine_version,
        },
        calculatedValues={
            "compressibilityFactor": Quantity(value=s.compressibility_factor, unit="dimensionless"),
            "density": Quantity(value=s.density_kg_m3, unit="kg/m3"),
            "molarMass": Quantity(value=s.molar_mass_kg_kmol, unit="kg/kmol"),
            "specificHeatCp": Quantity(value=s.specific_heat_cp_kj_kgk, unit="kJ/(kg*K)"),
            "jouleThomsonCoefficient": Quantity(value=s.joule_thomson_k_mpa, unit="K/MPa"),
            "speedOfSound": Quantity(value=s.speed_of_sound_m_s, unit="m/s"),
        },
        validation=ValidationBlock(
            status="SUCCESS_VALID" if result.is_within_model_range else "SUCCESS_WITH_WARNINGS",
            isWithinModelRange=result.is_within_model_range,
            warnings=result.warnings,
        ),
    )


@router.post("/combustion", response_model=CombustionResponse)
def combustion(req: CombustionRequest) -> CombustionResponse:
    try:
        composition = GasComposition.from_mapping(req.gasComposition)
        result = combustion_properties(composition, req.referencePair)
    except (CompositionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return CombustionResponse(
        referencePair=result.reference_pair,
        grossCalorificValue=Quantity(value=result.gross_calorific_value_mj_m3, unit="MJ/m3"),
        netCalorificValue=Quantity(value=result.net_calorific_value_mj_m3, unit="MJ/m3"),
        relativeDensity=result.relative_density,
        wobbeIndex=Quantity(value=result.wobbe_index_mj_m3, unit="MJ/m3"),
    )
