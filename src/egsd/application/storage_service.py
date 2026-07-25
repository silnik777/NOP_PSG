"""Energy-storage service: CAES round-trip plus a thin re-export of pipeline linepack.

This groups the network's storage options in one place (as requested: linepack together
with CAES), both of which feed the LCOS indicator in the finance module (Faza III).
"""

from __future__ import annotations

from ..domain.storage.models import CaesInput, CaesResult
from ..domain.thermo.compression import ResultClass
from ..infrastructure.gas_engine.cache import CachingGasEngine
from ..infrastructure.gas_engine.coolprop_engine import CoolPropGasEngine
from .hydraulics_service import HydraulicsService
from .thermo_ops import compress_multistage, expand_multistage

_J_PER_KWH = 3.6e6
_MWH_PER_KWH = 1e-3


class StorageService:
    def __init__(self, engine: CachingGasEngine | CoolPropGasEngine | None = None) -> None:
        self._engine = engine or CachingGasEngine()
        # Linepack reuses the hydraulics service (single source of the pipeline calc).
        self.hydraulics = HydraulicsService(self._engine)

    @property
    def engine_version(self) -> str:
        return self._engine.engine_version

    def caes(self, data: CaesInput) -> CaesResult:
        comp = data.composition
        inner = self._engine.inner if isinstance(self._engine, CachingGasEngine) else self._engine

        rho_max = self._engine.point_properties(
            comp, data.max_pressure_mpa, data.storage_temperature_k
        ).state.density_kg_m3
        rho_min = self._engine.point_properties(
            comp, data.min_pressure_mpa, data.storage_temperature_k
        ).state.density_kg_m3

        mass_max = data.cavern_volume_m3 * rho_max  # kg
        working_mass = data.cavern_volume_m3 * (rho_max - rho_min)  # kg deliverable

        # Charge: intercooled multi-stage compression from ambient up to cavern max pressure.
        charge = compress_multistage(
            inner, comp, data.ambient_pressure_mpa, data.ambient_temperature_k,
            data.max_pressure_mpa, data.charge_isentropic_efficiency, data.compression_stages,
        )
        # Discharge: reheated multi-stage expansion from cavern pressure down to ambient.
        discharge = expand_multistage(
            inner, comp, data.max_pressure_mpa, data.storage_temperature_k,
            data.ambient_pressure_mpa, data.discharge_isentropic_efficiency, data.expansion_stages,
        )

        charge_kwh = working_mass * charge.specific_work_kj_kg / _J_PER_KWH * 1000.0
        discharge_kwh = working_mass * discharge.specific_work_kj_kg / _J_PER_KWH * 1000.0
        round_trip = discharge_kwh / charge_kwh if charge_kwh > 0 else 0.0

        warnings = [
            "CAES energy is a screening estimate (no reheat / thermal storage modelled).",
        ]
        if discharge.outlet_temperature_k < 233.15:
            warnings.append(
                f"Turbine outlet {discharge.outlet_temperature_k:.1f} K is very low — a diabatic "
                "CAES plant would require pre-heating (fuel firing) not included here."
            )

        return CaesResult(
            stored_air_mass_max_tonnes=mass_max / 1000.0,
            working_air_mass_tonnes=working_mass / 1000.0,
            charge_energy_mwh=charge_kwh * _MWH_PER_KWH,
            discharge_energy_mwh=discharge_kwh * _MWH_PER_KWH,
            round_trip_efficiency=round_trip,
            discharge_outlet_temperature_k=discharge.outlet_temperature_k,
            result_class=ResultClass.SCREENING,
            warnings=tuple(warnings),
        )
