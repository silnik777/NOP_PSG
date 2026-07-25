"""Module IV endpoints: emergency blowdown (choked/subcritical, lumped inventory)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...application.outflow_service import OutflowService
from ...domain.gas.composition import CompositionError
from ...domain.outflow.models import BlowdownInput
from ...infrastructure.gas_engine.errors import EngineError
from ...infrastructure.persistence.database import get_session
from ..units import length_to_m, pressure_to_mpa, temperature_to_k
from .common import resolve_composition
from .schemas import Quantity

router = APIRouter(prefix="/api/v1/outflow", tags=["outflow"])

_service = OutflowService()


class BlowdownRequest(BaseModel):
    compositionId: str | None = None
    gasComposition: dict[str, float] | None = None
    initialPressure: Quantity
    gasTemperature: Quantity
    orificeDiameter: Quantity
    dischargeCoefficient: float = 0.62
    volume: Quantity | None = None  # m3
    pipeDiameter: Quantity | None = None
    pipeLength: Quantity | None = None
    maxDurationH: float = 48.0


class ProfilePointDTO(BaseModel):
    timeMin: float
    pressure: float
    massFlow: float
    choked: bool


class BlowdownResponse(BaseModel):
    totalReleased: Quantity
    releasedByComponent: dict[str, float]  # tonnes
    methaneReleased: Quantity
    hydrogenReleased: Quantity
    co2eScope1: Quantity
    timeToAtmospheric: Quantity | None  # minutes
    initialInventory: Quantity
    residualInventory: Quantity
    peakMassFlow: Quantity
    profile: list[ProfilePointDTO]
    resultClass: str
    warnings: list[str] = []


@router.post("/blowdown", response_model=BlowdownResponse)
def blowdown(req: BlowdownRequest, session: Session = Depends(get_session)) -> BlowdownResponse:
    try:
        composition = resolve_composition(req.compositionId, req.gasComposition, session)
        data = BlowdownInput(
            composition=composition,
            initial_pressure_mpa=pressure_to_mpa(
                req.initialPressure.value, req.initialPressure.unit
            ),
            gas_temperature_k=temperature_to_k(req.gasTemperature.value, req.gasTemperature.unit),
            orifice_diameter_m=length_to_m(req.orificeDiameter.value, req.orificeDiameter.unit),
            discharge_coefficient=req.dischargeCoefficient,
            volume_m3=req.volume.value if req.volume else None,
            pipe_diameter_m=(
                length_to_m(req.pipeDiameter.value, req.pipeDiameter.unit)
                if req.pipeDiameter else None
            ),
            pipe_length_m=(
                length_to_m(req.pipeLength.value, req.pipeLength.unit)
                if req.pipeLength else None
            ),
            max_duration_h=req.maxDurationH,
        )
        result = _service.blowdown(data)
    except (CompositionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EngineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return BlowdownResponse(
        totalReleased=Quantity(value=result.total_released_tonnes, unit="t"),
        releasedByComponent=result.released_by_component_tonnes,
        methaneReleased=Quantity(value=result.methane_released_tonnes, unit="t"),
        hydrogenReleased=Quantity(value=result.hydrogen_released_tonnes, unit="t"),
        co2eScope1=Quantity(value=result.co2e_scope1_tonnes, unit="t CO2e"),
        timeToAtmospheric=(
            Quantity(value=result.time_to_atmospheric_min, unit="min")
            if result.time_to_atmospheric_min is not None else None
        ),
        initialInventory=Quantity(value=result.initial_inventory_tonnes, unit="t"),
        residualInventory=Quantity(value=result.residual_inventory_tonnes, unit="t"),
        peakMassFlow=Quantity(value=result.peak_mass_flow_kg_s, unit="kg/s"),
        profile=[
            ProfilePointDTO(
                timeMin=p.time_min, pressure=p.pressure_mpa,
                massFlow=p.mass_flow_kg_s, choked=p.choked,
            )
            for p in result.profile
        ],
        resultClass=result.result_class.value,
        warnings=list(result.warnings),
    )
