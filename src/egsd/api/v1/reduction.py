"""Module III endpoints: reduction station (throttle vs expander, preheat, p-T margin)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...application.reduction_service import ReductionService
from ...domain.gas.composition import CompositionError
from ...domain.reduction.models import ReductionInput
from ...infrastructure.gas_engine.errors import EngineError
from ...infrastructure.persistence.database import get_session
from ..units import mass_flow_to_kg_s, pressure_to_mpa, temperature_to_k
from .common import resolve_composition
from .schemas import Quantity

router = APIRouter(prefix="/api/v1/reduction", tags=["reduction"])

_service = ReductionService()


class ReductionRequest(BaseModel):
    compositionId: str | None = None
    gasComposition: dict[str, float] | None = None
    massFlowRate: Quantity
    inletPressure: Quantity
    inletTemperature: Quantity
    outletPressureTarget: Quantity
    minOutletTemperature: Quantity | None = None
    expanderIsentropicEfficiency: float = 0.85


class ThrottleDTO(BaseModel):
    outletTemperature: Quantity
    temperatureDrop: Quantity
    preheatRequired: bool
    preheatInletTemperature: Quantity | None
    preheaterDuty: Quantity | None


class ExpanderDTO(BaseModel):
    recoveredPower: Quantity
    outletTemperature: Quantity
    preheatRequired: bool
    preheatInletTemperature: Quantity | None
    preheaterDuty: Quantity | None
    netEnergyNote: str


class PtPointDTO(BaseModel):
    pressure: float
    temperature: float
    dewTemperature: float | None
    margin: float | None


class ReductionResponse(BaseModel):
    throttle: ThrottleDTO
    expander: ExpanderDTO
    ptPath: list[PtPointDTO]
    phaseEnvelopeAvailable: bool
    resultClass: str
    warnings: list[str] = []


def _q(value: float | None, unit: str) -> Quantity | None:
    return Quantity(value=value, unit=unit) if value is not None else None


@router.post("/station", response_model=ReductionResponse)
def station(req: ReductionRequest, session: Session = Depends(get_session)) -> ReductionResponse:
    try:
        composition = resolve_composition(req.compositionId, req.gasComposition, session)
        kwargs = dict(
            composition=composition,
            mass_flow_kg_s=mass_flow_to_kg_s(req.massFlowRate.value, req.massFlowRate.unit),
            inlet_pressure_mpa=pressure_to_mpa(req.inletPressure.value, req.inletPressure.unit),
            inlet_temperature_k=temperature_to_k(
                req.inletTemperature.value, req.inletTemperature.unit
            ),
            outlet_pressure_mpa=pressure_to_mpa(
                req.outletPressureTarget.value, req.outletPressureTarget.unit
            ),
            expander_isentropic_efficiency=req.expanderIsentropicEfficiency,
        )
        if req.minOutletTemperature is not None:
            kwargs["min_outlet_temperature_k"] = temperature_to_k(
                req.minOutletTemperature.value, req.minOutletTemperature.unit
            )
        result = _service.station(ReductionInput(**kwargs))
    except (CompositionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EngineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    t, e = result.throttle, result.expander
    return ReductionResponse(
        throttle=ThrottleDTO(
            outletTemperature=Quantity(value=t.outlet_temperature_k, unit="K"),
            temperatureDrop=Quantity(value=t.temperature_drop_k, unit="K"),
            preheatRequired=t.preheat_required,
            preheatInletTemperature=_q(t.preheat_inlet_temperature_k, "K"),
            preheaterDuty=_q(t.preheater_duty_kw, "kW"),
        ),
        expander=ExpanderDTO(
            recoveredPower=Quantity(value=e.recovered_power_kw, unit="kW"),
            outletTemperature=Quantity(value=e.outlet_temperature_k, unit="K"),
            preheatRequired=e.preheat_required,
            preheatInletTemperature=_q(e.preheat_inlet_temperature_k, "K"),
            preheaterDuty=_q(e.preheater_duty_kw, "kW"),
            netEnergyNote=e.net_energy_note,
        ),
        ptPath=[
            PtPointDTO(
                pressure=p.pressure_mpa, temperature=p.temperature_k,
                dewTemperature=p.dew_temperature_k, margin=p.margin_k,
            )
            for p in result.pt_path
        ],
        phaseEnvelopeAvailable=result.phase_envelope_available,
        resultClass=result.result_class.value,
        warnings=list(result.warnings),
    )
