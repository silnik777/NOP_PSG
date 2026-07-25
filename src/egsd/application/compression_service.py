"""Module I — compression calculation (real-fluid, isentropic-efficiency method).

Method (matches test case TV-M1-001):
  1. inlet state at (p_in, T_in) -> h_in, s_in
  2. isentropic outlet: T_out_s such that s(p_out, T_out_s) = s_in -> h_out_s
  3. actual: h_out = h_in + (h_out_s - h_in) / eta_iz
  4. shaft power P = m_dot * (h_out - h_in) / eta_mech ; T_out from h(p_out, T_out) = h_out

All states come from the GasPropertyEngine (single source of thermodynamic truth).
"""

from __future__ import annotations

from ..domain.gas.bounds import check_point, is_hard_out_of_range
from ..domain.thermo.compression import (
    CompressionInput,
    CompressionResult,
    ResultClass,
    ValidationStatus,
)
from ..infrastructure.gas_engine.coolprop_engine import CoolPropGasEngine
from ..infrastructure.gas_engine.errors import OutOfRangeError

# Search span for the outlet-temperature Brent solve.
_T_SPAN_K = 500.0


class CompressionService:
    def __init__(self, engine: CoolPropGasEngine | None = None) -> None:
        self._engine = engine or CoolPropGasEngine()

    @property
    def engine_version(self) -> str:
        return self._engine.engine_version

    def calculate(self, data: CompressionInput) -> CompressionResult:
        comp = data.composition
        p_in, t_in, p_out = (
            data.inlet_pressure_mpa,
            data.inlet_temperature_k,
            data.outlet_pressure_mpa,
        )
        for p in (p_in, p_out):
            if is_hard_out_of_range(p):
                raise OutOfRangeError(
                    f"Pressure {p} MPa outside absolute cutoff (0 < p <= 35 MPa) — aborted (W3.4)."
                )

        inlet = self._engine.point_properties(comp, p_in, t_in).state
        h_in, s_in = inlet.enthalpy_kj_kg, inlet.entropy_kj_kgk

        # 2. isentropic outlet temperature and enthalpy
        t_out_s = self._engine.temperature_at_ps(comp, p_out, s_in, t_in, t_in + _T_SPAN_K)
        h_out_s = self._engine.enthalpy_kj_kg(comp, p_out, t_out_s)
        isentropic_head = h_out_s - h_in

        # 3. actual enthalpy rise
        actual_head = isentropic_head / data.isentropic_efficiency
        h_out = h_in + actual_head

        # 4. actual outlet temperature and shaft power
        t_out = self._engine.temperature_at_ph(comp, p_out, h_out, t_in, t_in + _T_SPAN_K)
        shaft_power_kw = data.mass_flow_kg_s * actual_head / data.mechanical_efficiency

        status, warnings = self._validate(p_in, t_in, p_out, t_out)
        return CompressionResult(
            required_shaft_power_kw=shaft_power_kw,
            outlet_temperature_k=t_out,
            polytropic_head_kj_kg=actual_head,
            isentropic_head_kj_kg=isentropic_head,
            validation_status=status,
            result_class=ResultClass.ENGINEERING,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _validate(
        p_in: float, t_in: float, p_out: float, t_out: float
    ) -> tuple[ValidationStatus, list[str]]:
        warnings: list[str] = []
        for label, p, t in (("inlet", p_in, t_in), ("outlet", p_out, t_out)):
            warnings.extend(f"{label}: {v.message}" for v in check_point(p, t))
        # Pipe-coating temperature guard (OPZ Karta Modułu I: T_max <= 50 degC = 323.15 K).
        if t_out > 323.15:
            warnings.append(
                f"outlet temperature {t_out:.1f} K exceeds 323.15 K (50 degC) — gas cooler likely "
                "required to protect pipeline coating."
            )
        status = ValidationStatus.VALID_WITHIN_BOUNDS if not warnings else (
            ValidationStatus.VALID_WITH_WARNINGS
        )
        return status, warnings
