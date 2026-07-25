"""Device technology endpoints: catalog listing and compressor/expander selection."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...application.device_selection_service import (
    DutySpec,
    compression_auxiliaries,
    expansion_auxiliaries,
    reducer_split,
    select,
)
from ...application.thermo_ops import compress_multistage, expand, expand_multistage
from ...domain.devices.models import MachineRole
from ...domain.gas.composition import CompositionError
from ...infrastructure.gas_engine.cache import CachingGasEngine
from ...infrastructure.gas_engine.errors import EngineError
from ...infrastructure.persistence.database import get_session
from ...infrastructure.persistence.device_repository import list_device_cards
from ..units import mass_flow_to_kg_s, pressure_to_mpa, temperature_to_k
from .common import resolve_composition
from .schemas import (
    AuxiliaryDTO,
    DeviceCandidateDTO,
    DeviceCardDTO,
    DeviceSelectRequest,
    Quantity,
    SelectCompressorResponse,
    SelectExpanderResponse,
)

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])

_engine = CachingGasEngine()


def _card_dto(card) -> DeviceCardDTO:
    return DeviceCardDTO(
        code=card.code, name=card.name, role=card.role.value, category=card.category.value,
        stageRatioMin=card.stage_ratio_min, stageRatioMax=card.stage_ratio_max,
        stageRatioOptimal=card.stage_ratio_optimal,
        isentropicEfficiencyNominal=card.isentropic_efficiency_nominal,
        massFlowMin=Quantity(value=card.mass_flow_min_kg_s, unit="kg/s"),
        massFlowMax=Quantity(value=card.mass_flow_max_kg_s, unit="kg/s"),
        notes=card.notes,
    )


def _candidate_dto(c) -> DeviceCandidateDTO:
    return DeviceCandidateDTO(
        code=c.card.code, name=c.card.name, category=c.card.category.value,
        feasible=c.feasible, stages=c.stages, stageRatio=round(c.stage_ratio, 4),
        effectiveEfficiency=round(c.effective_efficiency, 4), reason=c.reason,
    )


def _aux_dto(a) -> AuxiliaryDTO:
    return AuxiliaryDTO(
        kind=a.kind, description=a.description,
        duty=Quantity(value=round(a.duty_kw, 2), unit="kW") if a.duty_kw is not None else None,
        source=a.source,
    )


@router.get("", response_model=list[DeviceCardDTO])
def list_devices(
    role: str | None = Query(None, description="Compressor | Expander"),
    session: Session = Depends(get_session),
) -> list[DeviceCardDTO]:
    role_enum = MachineRole(role) if role else None
    return [_card_dto(c) for c in list_device_cards(session, role_enum)]


def _duty_inputs(req: DeviceSelectRequest, session: Session):
    comp = resolve_composition(req.compositionId, req.gasComposition, session)
    mdot = mass_flow_to_kg_s(req.massFlowRate.value, req.massFlowRate.unit)
    p_in = pressure_to_mpa(req.inletPressure.value, req.inletPressure.unit)
    t_in = temperature_to_k(req.inletTemperature.value, req.inletTemperature.unit)
    p_out = pressure_to_mpa(req.outletPressureTarget.value, req.outletPressureTarget.unit)
    return comp, mdot, p_in, t_in, p_out


@router.post("/select-compressor", response_model=SelectCompressorResponse)
def select_compressor(
    req: DeviceSelectRequest, session: Session = Depends(get_session)
) -> SelectCompressorResponse:
    try:
        comp, mdot, p_in, t_in, p_out = _duty_inputs(req, session)
        if p_out <= p_in:
            raise ValueError("outlet pressure must exceed inlet pressure for a compressor.")
        cards = list_device_cards(session, MachineRole.COMPRESSOR)
        duty = DutySpec(
            overall_ratio=p_out / p_in, mass_flow_kg_s=mdot, role=MachineRole.COMPRESSOR
        )
        selected, ranked = select(cards, duty)
        if selected is None:
            raise HTTPException(status_code=422, detail="No feasible compressor for this duty.")

        work = compress_multistage(
            _engine.inner, comp, p_in, t_in, p_out, selected.effective_efficiency, selected.stages
        )
        cp = _engine.point_properties(comp, p_in, t_in).state.specific_heat_cp_kj_kgk
        aux = compression_auxiliaries(selected.stages, mdot, cp, work.outlet_temperature_k)
        return SelectCompressorResponse(
            selected=_candidate_dto(selected),
            requiredShaftPower=Quantity(value=mdot * work.specific_work_kj_kg, unit="kW"),
            outletTemperature=Quantity(value=work.outlet_temperature_k, unit="K"),
            pressureRatio=p_out / p_in,
            auxiliaries=[_aux_dto(a) for a in aux],
            alternatives=[_candidate_dto(c) for c in ranked if c.card.code != selected.card.code],
            resultClass="Engineering",
        )
    except (CompositionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EngineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/select-expander", response_model=SelectExpanderResponse)
def select_expander(
    req: DeviceSelectRequest, session: Session = Depends(get_session)
) -> SelectExpanderResponse:
    try:
        comp, mdot, p_in, t_in, p_out = _duty_inputs(req, session)
        if p_out >= p_in:
            raise ValueError("outlet pressure must be below inlet pressure for an expander.")
        cards = list_device_cards(session, MachineRole.EXPANDER)
        duty = DutySpec(overall_ratio=p_in / p_out, mass_flow_kg_s=mdot, role=MachineRole.EXPANDER)
        selected, ranked = select(cards, duty)
        if selected is None:
            raise HTTPException(status_code=422, detail="No feasible expander for this duty.")

        # Recoverable power via a reheated multi-stage train.
        recovered = expand_multistage(
            _engine.inner, comp, p_in, t_in, p_out, selected.effective_efficiency, selected.stages
        )
        # Single-stage outlet temperature reveals the freezing/hydrate risk.
        single = expand(_engine.inner, comp, p_in, t_in, p_out, selected.effective_efficiency)
        cp = _engine.point_properties(comp, p_in, t_in).state.specific_heat_cp_kj_kgk
        aux = expansion_auxiliaries(mdot, cp, single.outlet_temperature_k, t_in)
        reducer = reducer_split(p_in, p_out, p_out, MachineRole.EXPANDER)
        if reducer is not None:
            aux.append(reducer)
        return SelectExpanderResponse(
            selected=_candidate_dto(selected),
            recoveredPower=Quantity(value=mdot * recovered.specific_work_kj_kg, unit="kW"),
            outletTemperatureSingleStage=Quantity(value=single.outlet_temperature_k, unit="K"),
            pressureRatio=p_in / p_out,
            auxiliaries=[_aux_dto(a) for a in aux],
            alternatives=[_candidate_dto(c) for c in ranked if c.card.code != selected.card.code],
            resultClass="Engineering",
        )
    except (CompositionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EngineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
