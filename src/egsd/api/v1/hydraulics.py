"""Hydraulics endpoints: Module II steady flow + linepack (Karta Modułu II)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...application.hydraulics_service import HydraulicsService
from ...domain.gas.composition import CompositionError
from ...domain.hydraulics.models import HydraulicsInput
from ...infrastructure.gas_engine.errors import OutOfRangeError, StateSolveError
from ...infrastructure.persistence.database import get_session
from ..units import (
    length_to_m,
    normal_flow_to_nm3_h,
    pressure_to_mpa,
    temperature_to_k,
)
from .common import resolve_composition
from .schemas import HydraulicsRequest, HydraulicsResponse, LinepackResponse, Quantity

logger = logging.getLogger("egsd.hydraulics")
router = APIRouter(prefix="/api/v1/hydraulics", tags=["hydraulics"])

_service = HydraulicsService()


def _build_input(req: HydraulicsRequest, session: Session) -> HydraulicsInput:
    composition = resolve_composition(req.compositionId, req.gasComposition, session)
    return HydraulicsInput(
        composition=composition,
        diameter_m=length_to_m(req.diameter.value, req.diameter.unit),
        roughness_m=length_to_m(req.roughness.value, req.roughness.unit),
        length_m=length_to_m(req.length.value, req.length.unit),
        inlet_pressure_mpa=pressure_to_mpa(req.inletPressure.value, req.inletPressure.unit),
        gas_temperature_k=temperature_to_k(req.gasTemperature.value, req.gasTemperature.unit),
        normal_flow_nm3_h=normal_flow_to_nm3_h(req.normalFlow.value, req.normalFlow.unit),
    )


@router.post("/steady-flow", response_model=HydraulicsResponse)
def steady_flow(
    req: HydraulicsRequest, session: Session = Depends(get_session)
) -> HydraulicsResponse:
    try:
        data = _build_input(req, session)
    except (CompositionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        r = _service.steady_flow(data)
    except OutOfRangeError as exc:
        logger.critical("Hydraulics rejected (out of range): %s", exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except StateSolveError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return HydraulicsResponse(
        outletPressure=Quantity(value=r.outlet_pressure_mpa, unit="MPa"),
        pressureDrop=Quantity(value=r.pressure_drop_mpa, unit="MPa"),
        massFlow=Quantity(value=r.mass_flow_kg_s, unit="kg/s"),
        averageVelocity=Quantity(value=r.average_velocity_m_s, unit="m/s"),
        reynoldsNumber=r.reynolds_number,
        frictionFactor=r.friction_factor,
        flowRegime=r.flow_regime.value,
        machNumber=r.mach_number,
        validationStatus=r.validation_status.value,
        resultClass=r.result_class.value,
        warnings=list(r.warnings),
    )


@router.post("/linepack", response_model=LinepackResponse)
def linepack(
    req: HydraulicsRequest, session: Session = Depends(get_session)
) -> LinepackResponse:
    try:
        data = _build_input(req, session)
    except (CompositionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        r = _service.linepack(data)
    except (OutOfRangeError, StateSolveError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return LinepackResponse(
        linepackMass=Quantity(value=r.linepack_mass_tonnes, unit="t"),
        linepackNormalVolume=Quantity(value=r.linepack_normal_volume_nm3, unit="Nm3"),
        averagePressure=Quantity(value=r.average_pressure_mpa, unit="MPa"),
        averageDensity=Quantity(value=r.average_density_kg_m3, unit="kg/m3"),
    )
