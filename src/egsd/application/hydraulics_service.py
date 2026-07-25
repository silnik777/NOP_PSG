"""Module II — hydraulics service (Colebrook-White + general gas-flow equation).

Physics (steady, isothermal, horizontal single segment):
  - Mass flow from normal volumetric flow: m_dot = Q_n * rho_n, rho_n from the engine at
    normal reference conditions (pinned base — verification finding #4).
  - Mass flux G = m_dot / A; Reynolds number Re = G * D / mu.
  - Darcy friction factor lambda from the Colebrook-White implicit equation (Brent).
  - General isothermal flow equation with acceleration term:
        P1^2 - P2^2 = G^2 * Z_avg * R_specific * T * (lambda * L / D + 2 ln(P1/P2))
    solved by fixed-point iteration on P2 (Z_avg, rho_avg, mu from the engine at P_avg).
  - Linepack = A * L * rho_avg (mass); normal volume = mass / rho_n.
"""

from __future__ import annotations

import math

from scipy.optimize import brentq

from ..domain.gas.bounds import is_hard_out_of_range
from ..domain.gas.composition import GasComposition
from ..domain.hydraulics.models import (
    NORMAL_PRESSURE_PA,
    NORMAL_TEMPERATURE_K,
    FlowRegime,
    HydraulicsInput,
    HydraulicsResult,
    LinepackResult,
)
from ..domain.thermo.compression import ResultClass, ValidationStatus
from ..infrastructure.gas_engine.cache import CachingGasEngine
from ..infrastructure.gas_engine.coolprop_engine import CoolPropGasEngine
from ..infrastructure.gas_engine.errors import OutOfRangeError, StateSolveError

_R = 8.314462618  # J/(mol*K)
_MAX_ITER = 100
_P2_TOL_PA = 1.0  # convergence tolerance on outlet pressure (Pa)


class HydraulicsService:
    def __init__(self, engine: CachingGasEngine | CoolPropGasEngine | None = None) -> None:
        self._engine = engine or CachingGasEngine()

    @property
    def engine_version(self) -> str:
        return self._engine.engine_version

    # ----- helpers ------------------------------------------------------------

    def _normal_density(self, comp: GasComposition) -> float:
        state = self._engine.point_properties(
            comp, NORMAL_PRESSURE_PA / 1e6, NORMAL_TEMPERATURE_K
        ).state
        return state.density_kg_m3

    @staticmethod
    def _colebrook_white(reynolds: float, rel_roughness: float) -> float:
        """Darcy friction factor from the implicit Colebrook-White equation."""
        if reynolds < 2300:  # laminar — Hagen-Poiseuille
            return 64.0 / reynolds

        def residual(lam: float) -> float:
            return 1.0 / math.sqrt(lam) + 2.0 * math.log10(
                rel_roughness / 3.7 + 2.51 / (reynolds * math.sqrt(lam))
            )

        return brentq(residual, 1e-4, 1.0, xtol=1e-10)

    @staticmethod
    def _regime(reynolds: float) -> FlowRegime:
        if reynolds < 2300:
            return FlowRegime.LAMINAR
        if reynolds < 4000:
            return FlowRegime.TRANSITIONAL
        return FlowRegime.TURBULENT

    # ----- main calculations --------------------------------------------------

    def steady_flow(self, data: HydraulicsInput) -> HydraulicsResult:
        if is_hard_out_of_range(data.inlet_pressure_mpa):
            raise OutOfRangeError(
                f"Inlet pressure {data.inlet_pressure_mpa} MPa outside cutoff (0 < p <= 35 MPa)."
            )
        comp = data.composition
        area = math.pi * data.diameter_m**2 / 4.0
        rho_n = self._normal_density(comp)
        mass_flow = data.normal_flow_nm3_h / 3600.0 * rho_n  # kg/s
        mass_flux = mass_flow / area  # G, kg/(m^2*s)
        rel_roughness = data.roughness_m / data.diameter_m
        p1_pa = data.inlet_pressure_mpa * 1e6
        t = data.gas_temperature_k

        friction = 0.0
        reynolds = 0.0
        converged = False
        p2_pa = 0.90 * p1_pa  # initial guess
        for _ in range(_MAX_ITER):
            p_avg_pa = self._average_pressure(p1_pa, p2_pa)
            state = self._engine.point_properties(comp, p_avg_pa / 1e6, t).state
            if state.viscosity_pa_s is None:
                raise StateSolveError(
                    "Viscosity unavailable for this mixture; a Lee-Gonzalez-Eakin correlation "
                    "is required (OPZ §3.2) before hydraulic calculation."
                )
            r_specific = _R / (state.molar_mass_kg_kmol / 1000.0)
            reynolds = mass_flux * data.diameter_m / state.viscosity_pa_s
            friction = self._colebrook_white(reynolds, rel_roughness)

            k = mass_flux**2 * state.compressibility_factor * r_specific * t
            accel = 2.0 * math.log(p1_pa / p2_pa)
            rhs = p1_pa**2 - k * (friction * data.length_m / data.diameter_m + accel)
            if rhs <= 0:
                raise StateSolveError(
                    "Flow demand exceeds pipeline capacity for the given inlet pressure "
                    "(outlet pressure would be non-physical). Reduce flow or increase inlet "
                    "pressure/diameter."
                )
            new_p2 = math.sqrt(rhs)
            if abs(new_p2 - p2_pa) < _P2_TOL_PA:
                p2_pa = new_p2
                converged = True
                break
            p2_pa = new_p2

        if not converged:
            # OPZ (Część A): operations must be blocked when the solver does not converge —
            # never silently return the last iterate.
            raise StateSolveError(
                f"Hydraulic solver did not converge within {_MAX_ITER} iterations "
                f"(last outlet-pressure step > {_P2_TOL_PA} Pa). Calculation blocked."
            )

        # Final average-state velocity and Mach number.
        final_state = self._engine.point_properties(
            comp, self._average_pressure(p1_pa, p2_pa) / 1e6, t
        ).state
        velocity = mass_flux / final_state.density_kg_m3
        mach = velocity / final_state.speed_of_sound_m_s

        status, warnings = self._validate(reynolds, mach, data)
        return HydraulicsResult(
            outlet_pressure_mpa=p2_pa / 1e6,
            pressure_drop_mpa=(p1_pa - p2_pa) / 1e6,
            mass_flow_kg_s=mass_flow,
            average_velocity_m_s=velocity,
            reynolds_number=reynolds,
            friction_factor=friction,
            flow_regime=self._regime(reynolds),
            mach_number=mach,
            validation_status=status,
            result_class=ResultClass.ENGINEERING,
            warnings=tuple(warnings),
        )

    def linepack(self, data: HydraulicsInput) -> LinepackResult:
        """Gas inventory stored in the segment (function of the static pressure profile)."""
        flow = self.steady_flow(data)
        comp = data.composition
        p1_pa = data.inlet_pressure_mpa * 1e6
        p2_pa = flow.outlet_pressure_mpa * 1e6
        p_avg_pa = self._average_pressure(p1_pa, p2_pa)
        avg_state = self._engine.point_properties(
            comp, p_avg_pa / 1e6, data.gas_temperature_k
        ).state
        area = math.pi * data.diameter_m**2 / 4.0
        volume_m3 = area * data.length_m
        mass = volume_m3 * avg_state.density_kg_m3
        rho_n = self._normal_density(comp)
        return LinepackResult(
            linepack_mass_tonnes=mass / 1000.0,
            linepack_normal_volume_nm3=mass / rho_n,
            average_pressure_mpa=p_avg_pa / 1e6,
            average_density_kg_m3=avg_state.density_kg_m3,
        )

    @staticmethod
    def _average_pressure(p1_pa: float, p2_pa: float) -> float:
        """Standard pipeline average pressure (accounts for the non-linear profile)."""
        return (2.0 / 3.0) * (p1_pa + p2_pa - (p1_pa * p2_pa) / (p1_pa + p2_pa))

    @staticmethod
    def _validate(
        reynolds: float, mach: float, data: HydraulicsInput
    ) -> tuple[ValidationStatus, list[str]]:
        warnings: list[str] = []
        if reynolds < 4000:
            warnings.append(
                f"Reynolds number {reynolds:.0f} is not fully turbulent; Colebrook-White "
                "applicability is reduced in the transitional/laminar regime."
            )
        if mach > 0.3:
            warnings.append(
                f"Mach number {mach:.2f} exceeds 0.3 — compressibility/acceleration effects are "
                "significant; treat the result as screening near this limit."
            )
        status = (
            ValidationStatus.VALID_WITHIN_BOUNDS
            if not warnings
            else ValidationStatus.VALID_WITH_WARNINGS
        )
        return status, warnings
