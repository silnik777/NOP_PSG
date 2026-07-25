"""Module IV — blowdown service: choked/subcritical orifice outflow, lumped inventory.

Method (per Karta Modułu IV, CFD explicitly excluded):
  - state (rho, Z, k=cp/cv, M) from the GasPropertyEngine at the current (p, T);
  - critical pressure ratio r_c = ((k+1)/2)^(k/(k-1)); flow is choked while p/p_amb >= r_c;
  - choked:      m_dot = Cd*A*sqrt(k*rho*p*(2/(k+1))^((k+1)/(k-1)))
  - subcritical: m_dot = Cd*A*sqrt(2*rho*p*k/(k-1)*(pr^(2/k) - pr^((k+1)/k))), pr = p_amb/p
  - lumped inventory: m -= m_dot*dt; pressure recovered from rho = m/V via the lagged
    real-gas relation p = Z(p_prev, T)*rho*R_specific*T (isothermal blowdown).
  - adaptive dt releasing ~2% of current inventory per step (geometric decay, bounded steps).

Scope-1 CO2e of the release is computed with the CoreEmissionEngine (AR6 GWP), tying
Module IV directly into the emission balance (OPZ §6 Scope 1).
"""

from __future__ import annotations

import math

from ..domain.emissions.models import EmissionInput
from ..domain.gas.bounds import is_hard_out_of_range
from ..domain.outflow.models import (
    BlowdownInput,
    BlowdownProfilePoint,
    BlowdownResult,
)
from ..domain.thermo.compression import ResultClass
from ..infrastructure.gas_engine.cache import CachingGasEngine
from ..infrastructure.gas_engine.coolprop_engine import CoolPropGasEngine
from ..infrastructure.gas_engine.errors import OutOfRangeError
from .emission_service import evaluate as evaluate_emissions

_R = 8.314462618  # J/(mol*K)
_MASS_STEP_FRACTION = 0.02  # release ~2% of current inventory per step
_MAX_STEPS = 5000
_STOP_PRESSURE_FACTOR = 1.02  # stop when p <= 1.02 * ambient
_PROFILE_EVERY = 10  # record every Nth step


class OutflowService:
    def __init__(self, engine: CachingGasEngine | CoolPropGasEngine | None = None) -> None:
        self._engine = engine or CachingGasEngine()

    @property
    def engine_version(self) -> str:
        return self._engine.engine_version

    def blowdown(self, data: BlowdownInput) -> BlowdownResult:
        if is_hard_out_of_range(data.initial_pressure_mpa):
            raise OutOfRangeError(
                f"Initial pressure {data.initial_pressure_mpa} MPa outside absolute cutoff."
            )
        comp = data.composition
        volume = data.inventory_volume_m3()
        area = math.pi * data.orifice_diameter_m**2 / 4.0
        t_gas = data.gas_temperature_k
        p_amb_pa = data.ambient_pressure_mpa * 1e6
        warnings: list[str] = []

        state = self._engine.point_properties(comp, data.initial_pressure_mpa, t_gas).state
        r_specific = _R / (state.molar_mass_kg_kmol / 1000.0)
        mass = volume * state.density_kg_m3  # kg
        initial_mass = mass
        p_pa = data.initial_pressure_mpa * 1e6

        elapsed_s = 0.0
        max_s = data.max_duration_h * 3600.0
        peak_flow = 0.0
        time_to_atm_s: float | None = None
        profile: list[BlowdownProfilePoint] = []

        for step in range(_MAX_STEPS):
            state = self._engine.point_properties(comp, p_pa / 1e6, t_gas).state
            rho = mass / volume
            k = max(1.01, state.specific_heat_cp_kj_kgk / state.specific_heat_cv_kj_kgk)
            z = state.compressibility_factor

            critical_ratio = ((k + 1.0) / 2.0) ** (k / (k - 1.0))
            choked = (p_pa / p_amb_pa) >= critical_ratio
            if choked:
                flow = (
                    data.discharge_coefficient * area
                    * math.sqrt(k * rho * p_pa * (2.0 / (k + 1.0)) ** ((k + 1.0) / (k - 1.0)))
                )
            else:
                pr = p_amb_pa / p_pa
                bracket = pr ** (2.0 / k) - pr ** ((k + 1.0) / k)
                if bracket <= 0:
                    break
                flow = (
                    data.discharge_coefficient * area
                    * math.sqrt(2.0 * rho * p_pa * k / (k - 1.0) * bracket)
                )
            peak_flow = max(peak_flow, flow)
            if flow <= 0:
                break

            dt = max(0.05, _MASS_STEP_FRACTION * mass / flow)
            dt = min(dt, max_s - elapsed_s)
            if step % _PROFILE_EVERY == 0:
                profile.append(
                    BlowdownProfilePoint(
                        time_min=round(elapsed_s / 60.0, 3),
                        pressure_mpa=round(p_pa / 1e6, 5),
                        mass_flow_kg_s=round(flow, 3),
                        choked=choked,
                    )
                )

            mass -= flow * dt
            elapsed_s += dt
            rho = mass / volume
            # Lagged real-gas pressure update (isothermal): p = Z*rho*R*T.
            p_pa = max(p_amb_pa, z * rho * r_specific * t_gas)

            if p_pa <= p_amb_pa * _STOP_PRESSURE_FACTOR:
                time_to_atm_s = elapsed_s
                break
            if elapsed_s >= max_s:
                warnings.append(
                    f"Nie osiągnięto ciśnienia atmosferycznego w {data.max_duration_h:.0f} h — "
                    "raportowany stan częściowego opróżnienia."
                )
                break
        else:
            warnings.append("Osiągnięto limit kroków symulacji — wynik częściowy.")

        released = initial_mass - mass
        # Split by mass fraction (composition constant during isothermal blowdown).
        mass_fractions = self._mass_fractions(comp, state.molar_mass_kg_kmol)
        by_component = {
            key: released * frac / 1000.0 for key, frac in mass_fractions.items()
        }
        ch4_t = by_component.get("methane", 0.0)
        h2_t = by_component.get("hydrogen", 0.0)
        emissions = evaluate_emissions(
            EmissionInput(methane_leak_tonnes=ch4_t, hydrogen_leak_tonnes=h2_t)
        )

        return BlowdownResult(
            total_released_tonnes=released / 1000.0,
            released_by_component_tonnes={k: round(v, 4) for k, v in by_component.items()},
            methane_released_tonnes=ch4_t,
            hydrogen_released_tonnes=h2_t,
            co2e_scope1_tonnes=emissions.breakdown.scope1_t_co2e,
            time_to_atmospheric_min=(
                round(time_to_atm_s / 60.0, 2) if time_to_atm_s is not None else None
            ),
            initial_inventory_tonnes=initial_mass / 1000.0,
            residual_inventory_tonnes=mass / 1000.0,
            peak_mass_flow_kg_s=peak_flow,
            profile=profile,
            result_class=ResultClass.ENGINEERING,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _mass_fractions(comp, molar_mass_mix_kg_kmol: float) -> dict[str, float]:
        from ..infrastructure.gas_engine.iso6976 import _COMPONENT_DATA

        out: dict[str, float] = {}
        for key, x in comp.fractions.items():
            m_i = _COMPONENT_DATA[key][2]  # molar mass, g/mol (full canonical set covered)
            out[key] = x * m_i / molar_mass_mix_kg_kmol
        # normalize tiny rounding drift
        total = sum(out.values())
        return {k: v / total for k, v in out.items()} if total > 0 else out
