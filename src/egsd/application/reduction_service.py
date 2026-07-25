"""Module III — pressure-reduction station: throttle vs expander, preheat, p-T margin.

All thermodynamic states come from the GasPropertyEngine. The throttle path is isenthalpic
(h = const); the expander path uses the isentropic-efficiency expansion from thermo_ops.
Preheater sizing solves the inlet temperature that keeps the *outlet* at the hydrate guard,
then converts the inlet enthalpy rise to duty.
"""

from __future__ import annotations

from scipy.optimize import brentq

from ..domain.gas.bounds import is_hard_out_of_range
from ..domain.gas.composition import GasComposition
from ..domain.reduction.models import (
    ExpanderAlternative,
    PtPathPoint,
    ReductionInput,
    ReductionResult,
    ThrottleResult,
)
from ..domain.thermo.compression import ResultClass
from ..infrastructure.gas_engine.cache import CachingGasEngine
from ..infrastructure.gas_engine.coolprop_engine import CoolPropGasEngine
from ..infrastructure.gas_engine.errors import OutOfRangeError
from .thermo_ops import expand

_PATH_POINTS = 12
_T_SEARCH_SPAN_K = 250.0
_MAX_PREHEAT_INLET_K = 423.15  # 150 degC — sanity cap for preheater solving


class ReductionService:
    def __init__(self, engine: CachingGasEngine | CoolPropGasEngine | None = None) -> None:
        self._engine = engine or CachingGasEngine()

    @property
    def engine_version(self) -> str:
        return self._engine.engine_version

    def _inner(self) -> CoolPropGasEngine:
        return self._engine.inner if isinstance(self._engine, CachingGasEngine) else self._engine

    # ----- throttling ----------------------------------------------------------

    def _throttle_outlet_t(
        self, comp: GasComposition, p_out: float, h_in_kj_kg: float, t_hint: float
    ) -> float:
        return self._inner().temperature_at_ph(
            comp, p_out, h_in_kj_kg,
            max(90.0, t_hint - _T_SEARCH_SPAN_K), t_hint + 30.0,
        )

    def _preheat_for_target(
        self,
        comp: GasComposition,
        data: ReductionInput,
        outlet_t_of_inlet_t,  # callable: inlet T -> outlet T
    ) -> tuple[float | None, float | None]:
        """Inlet temperature and preheater duty so the outlet hits the guard temperature."""
        target = data.min_outlet_temperature_k

        def gap(t_in: float) -> float:
            return outlet_t_of_inlet_t(t_in) - target

        if gap(data.inlet_temperature_k) >= 0:
            return None, None  # no preheat needed
        if gap(_MAX_PREHEAT_INLET_K) < 0:
            return None, None  # unreachable within sanity cap — caller adds a warning
        t_needed = brentq(gap, data.inlet_temperature_k, _MAX_PREHEAT_INLET_K, xtol=1e-4)
        inner = self._inner()
        h_cold = inner.enthalpy_kj_kg(comp, data.inlet_pressure_mpa, data.inlet_temperature_k)
        h_hot = inner.enthalpy_kj_kg(comp, data.inlet_pressure_mpa, t_needed)
        duty_kw = data.mass_flow_kg_s * (h_hot - h_cold)
        return t_needed, duty_kw

    # ----- main -----------------------------------------------------------------

    def station(self, data: ReductionInput) -> ReductionResult:
        for p in (data.inlet_pressure_mpa, data.outlet_pressure_mpa):
            if is_hard_out_of_range(p):
                raise OutOfRangeError(
                    f"Pressure {p} MPa outside absolute cutoff (0 < p <= 35 MPa) — aborted."
                )
        comp = data.composition
        inner = self._inner()
        warnings: list[str] = []

        # Throttle (isenthalpic).
        h_in = inner.enthalpy_kj_kg(comp, data.inlet_pressure_mpa, data.inlet_temperature_k)
        t_throttle = self._throttle_outlet_t(
            comp, data.outlet_pressure_mpa, h_in, data.inlet_temperature_k
        )

        def throttle_outlet(t_in: float) -> float:
            h = inner.enthalpy_kj_kg(comp, data.inlet_pressure_mpa, t_in)
            return self._throttle_outlet_t(comp, data.outlet_pressure_mpa, h, t_in)

        throttle_needs_heat = t_throttle < data.min_outlet_temperature_k
        t_pre_thr, duty_thr = (
            self._preheat_for_target(comp, data, throttle_outlet)
            if throttle_needs_heat
            else (None, None)
        )
        if throttle_needs_heat and t_pre_thr is None:
            warnings.append(
                "Podgrzew dla dławienia nieosiągalny w rozsądnym zakresie (do 150 °C) — "
                "sprawdź parametry stacji."
            )

        throttle = ThrottleResult(
            outlet_temperature_k=t_throttle,
            temperature_drop_k=data.inlet_temperature_k - t_throttle,
            preheat_required=throttle_needs_heat,
            preheat_inlet_temperature_k=t_pre_thr,
            preheater_duty_kw=duty_thr,
        )

        # Expander alternative (isentropic-efficiency expansion, shaft power out).
        eta = data.expander_isentropic_efficiency
        exp_result = expand(
            inner, comp, data.inlet_pressure_mpa, data.inlet_temperature_k,
            data.outlet_pressure_mpa, eta,
        )
        recovered_kw = data.mass_flow_kg_s * exp_result.specific_work_kj_kg

        def expander_outlet(t_in: float) -> float:
            return expand(
                inner, comp, data.inlet_pressure_mpa, t_in, data.outlet_pressure_mpa, eta
            ).outlet_temperature_k

        expander_needs_heat = exp_result.outlet_temperature_k < data.min_outlet_temperature_k
        t_pre_exp, duty_exp = (
            self._preheat_for_target(comp, data, expander_outlet)
            if expander_needs_heat
            else (None, None)
        )
        if expander_needs_heat and t_pre_exp is None:
            warnings.append(
                "Podgrzew dla ekspandera nieosiągalny w rozsądnym zakresie (do 150 °C)."
            )
        net_note = ""
        if duty_exp is not None:
            net_note = (
                f"Odzysk {recovered_kw:.0f} kW el./mech. wymaga podgrzewu ~{duty_exp:.0f} kW "
                "ciepła — bilans netto zależy od dostępnego źródła ciepła (odpadowe vs opalane)."
            )
        expander = ExpanderAlternative(
            recovered_power_kw=recovered_kw,
            outlet_temperature_k=exp_result.outlet_temperature_k,
            preheat_required=expander_needs_heat,
            preheat_inlet_temperature_k=t_pre_exp,
            preheater_duty_kw=duty_exp,
            net_energy_note=net_note,
        )

        # p-T path of the throttle (isenthalpic) against the dew line.
        envelope = self._inner().phase_envelope(comp)
        path = self._pt_path(comp, data, h_in, envelope)
        if envelope is None:
            warnings.append(
                "Nie udało się wyznaczyć obwiedni fazowej — margines do strefy dwufazowej "
                "nieznany (traktować ostrożnie, nie jako bezpieczny)."
            )

        return ReductionResult(
            throttle=throttle,
            expander=expander,
            pt_path=path,
            phase_envelope_available=envelope is not None,
            result_class=ResultClass.ENGINEERING,
            warnings=tuple(warnings),
        )

    def _pt_path(
        self,
        comp: GasComposition,
        data: ReductionInput,
        h_in_kj_kg: float,
        envelope: list[tuple[float, float]] | None,
    ) -> list[PtPathPoint]:
        points: list[PtPathPoint] = []
        p_in, p_out = data.inlet_pressure_mpa, data.outlet_pressure_mpa
        t_prev = data.inlet_temperature_k
        for i in range(_PATH_POINTS):
            p = p_in + (p_out - p_in) * i / (_PATH_POINTS - 1)
            t = (
                data.inlet_temperature_k
                if i == 0
                else self._throttle_outlet_t(comp, p, h_in_kj_kg, t_prev)
            )
            t_prev = t
            dew = self._dew_temperature_at(envelope, p)
            points.append(
                PtPathPoint(
                    pressure_mpa=round(p, 5),
                    temperature_k=round(t, 3),
                    dew_temperature_k=round(dew, 3) if dew is not None else None,
                    margin_k=round(t - dew, 3) if dew is not None else None,
                )
            )
        return points

    @staticmethod
    def _dew_temperature_at(
        envelope: list[tuple[float, float]] | None, p_mpa: float, band: float = 0.35
    ) -> float | None:
        """Warmest two-phase-boundary temperature near this pressure (conservative dew T)."""
        if not envelope:
            return None
        nearby = [t for t, pe in envelope if abs(pe - p_mpa) <= band]
        return max(nearby) if nearby else None
