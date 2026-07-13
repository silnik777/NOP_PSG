"""Thermo endpoints: Module I compression (Karta Modułu I)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...application.compression_service import CompressionService
from ...domain.gas.composition import CompositionError, GasComposition
from ...domain.thermo.compression import CompressionInput
from ...infrastructure.gas_engine.errors import OutOfRangeError, StateSolveError
from ...infrastructure.persistence.database import get_session
from ...infrastructure.persistence.models import ReferenceGasProfileRow
from ..units import mass_flow_to_kg_s, pressure_to_mpa, temperature_to_k
from .schemas import CompressionRequest, CompressionResponse, Quantity

logger = logging.getLogger("egsd.thermo")
router = APIRouter(prefix="/api/v1/thermo", tags=["thermo"])

_service = CompressionService()


def _resolve_composition(req: CompressionRequest, session: Session) -> GasComposition:
    if req.gasComposition:
        return GasComposition.from_mapping(req.gasComposition)
    if req.compositionId:
        row = session.scalar(
            select(ReferenceGasProfileRow).where(ReferenceGasProfileRow.code == req.compositionId)
        )
        if row is None:
            raise CompositionError(f"Unknown reference profile: {req.compositionId!r}")
        return GasComposition.from_mapping(row.fractions)
    raise CompositionError("Provide either gasComposition or compositionId.")


@router.post("/compression", response_model=CompressionResponse)
def compression(
    req: CompressionRequest, session: Session = Depends(get_session)
) -> CompressionResponse:
    try:
        composition = _resolve_composition(req, session)
        data = CompressionInput(
            composition=composition,
            mass_flow_kg_s=mass_flow_to_kg_s(req.massFlowRate.value, req.massFlowRate.unit),
            inlet_pressure_mpa=pressure_to_mpa(req.inletPressure.value, req.inletPressure.unit),
            inlet_temperature_k=temperature_to_k(
                req.inletTemperature.value, req.inletTemperature.unit
            ),
            outlet_pressure_mpa=pressure_to_mpa(
                req.outletPressureTarget.value, req.outletPressureTarget.unit
            ),
            isentropic_efficiency=req.isentropicEfficiency,
            mechanical_efficiency=req.mechanicalEfficiency,
        )
    except (CompositionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        result = _service.calculate(data)
    except OutOfRangeError as exc:
        logger.critical("Compression rejected (out of range): %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except StateSolveError as exc:
        logger.error("Compression solve failed: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return CompressionResponse(
        requiredShaftPower=Quantity(value=result.required_shaft_power_kw, unit="kW"),
        outletTemperature=Quantity(value=result.outlet_temperature_k, unit="K"),
        polytropicHead=Quantity(value=result.polytropic_head_kj_kg, unit="kJ/kg"),
        isentropicHead=Quantity(value=result.isentropic_head_kj_kg, unit="kJ/kg"),
        validationStatus=result.validation_status.value,
        resultClass=result.result_class.value,
        warnings=list(result.warnings),
    )
