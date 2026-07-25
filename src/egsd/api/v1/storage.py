"""Storage endpoints: CAES (compressed air energy storage) and pipeline linepack."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ...application.storage_service import StorageService
from ...domain.gas.composition import CompositionError, GasComposition
from ...domain.storage.models import CaesInput, air_composition
from ...infrastructure.gas_engine.errors import EngineError
from ...infrastructure.persistence.database import get_session
from ..units import pressure_to_mpa, temperature_to_k
from .hydraulics import _build_input  # reuse the hydraulics input builder for linepack
from .schemas import CaesRequest, CaesResponse, HydraulicsRequest, LinepackResponse, Quantity

router = APIRouter(prefix="/api/v1/storage", tags=["storage"])

_service = StorageService()


@router.post("/caes", response_model=CaesResponse)
def caes(req: CaesRequest) -> CaesResponse:
    try:
        composition = (
            GasComposition.from_mapping(req.gasComposition)
            if req.gasComposition
            else air_composition()
        )
        data = CaesInput(
            cavern_volume_m3=_volume(req),
            max_pressure_mpa=pressure_to_mpa(req.maxPressure.value, req.maxPressure.unit),
            min_pressure_mpa=pressure_to_mpa(req.minPressure.value, req.minPressure.unit),
            storage_temperature_k=_opt_temp(req.storageTemperature, 313.15),
            ambient_pressure_mpa=(
                pressure_to_mpa(req.ambientPressure.value, req.ambientPressure.unit)
                if req.ambientPressure
                else 0.101325
            ),
            ambient_temperature_k=_opt_temp(req.ambientTemperature, 288.15),
            charge_isentropic_efficiency=req.chargeIsentropicEfficiency,
            discharge_isentropic_efficiency=req.dischargeIsentropicEfficiency,
            compression_stages=req.compressionStages,
            expansion_stages=req.expansionStages,
            composition=composition,
        )
        result = _service.caes(data)
    except (CompositionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EngineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return CaesResponse(
        storedAirMassMax=Quantity(value=result.stored_air_mass_max_tonnes, unit="t"),
        workingAirMass=Quantity(value=result.working_air_mass_tonnes, unit="t"),
        chargeEnergy=Quantity(value=result.charge_energy_mwh, unit="MWh"),
        dischargeEnergy=Quantity(value=result.discharge_energy_mwh, unit="MWh"),
        roundTripEfficiency=result.round_trip_efficiency,
        dischargeOutletTemperature=Quantity(
            value=result.discharge_outlet_temperature_k, unit="K"
        ),
        resultClass=result.result_class.value,
        warnings=list(result.warnings),
    )


@router.post("/linepack", response_model=LinepackResponse)
def linepack(
    req: HydraulicsRequest, session: Session = Depends(get_session)
) -> LinepackResponse:
    try:
        data = _build_input(req, session)
        r = _service.hydraulics.linepack(data)
    except (CompositionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EngineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return LinepackResponse(
        linepackMass=Quantity(value=r.linepack_mass_tonnes, unit="t"),
        linepackNormalVolume=Quantity(value=r.linepack_normal_volume_nm3, unit="Nm3"),
        averagePressure=Quantity(value=r.average_pressure_mpa, unit="MPa"),
        averageDensity=Quantity(value=r.average_density_kg_m3, unit="kg/m3"),
    )


def _volume(req: CaesRequest) -> float:
    unit = req.cavernVolume.unit
    if unit in ("m3", "m^3"):
        return req.cavernVolume.value
    if unit in ("km3", "km^3"):
        return req.cavernVolume.value * 1e9
    raise ValueError(f"Unsupported volume unit {unit!r}")


def _opt_temp(q, default_k: float) -> float:
    return temperature_to_k(q.value, q.unit) if q is not None else default_k
