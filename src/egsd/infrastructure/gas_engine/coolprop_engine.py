"""CoolProp-backed GasPropertyEngine (HEOS / GERG-2008 binary parameters).

Design notes:
- Stateless and single-threaded per call (ADR 0001 — deterministic results).
- Uses the multi-fluid Helmholtz (`HEOS`) backend, which applies GERG-2008 (ISO 20765-1)
  reducing functions and departure terms for natural-gas + hydrogen components.
- CoolProp's mixture enthalpy/entropy flashes are numerically fragile at some conditions,
  so outlet states are resolved with a robust Brent solve over temperature on a PT basis.
"""

from __future__ import annotations

from CoolProp import CoolProp as CP
from CoolProp.CoolProp import AbstractState
from scipy.optimize import brentq

from ...domain.gas.bounds import check_point, is_hard_out_of_range
from ...domain.gas.composition import GasComposition
from ...domain.gas.properties import PointPropertiesResult, StatePoint
from .errors import OutOfRangeError, StateSolveError

ENGINE_VERSION = "gpe-core-1.0.0-heos"
MODEL_KEY = "GERG-2008"
_R = 8.314462618  # J/(mol*K)
_BRENT_XTOL = 1e-8


class CoolPropGasEngine:
    """Adapter over CoolProp. One AbstractState is built per composition."""

    engine_version = ENGINE_VERSION
    model_key = MODEL_KEY

    def _state(self, composition: GasComposition) -> AbstractState:
        names = "&".join(composition.coolprop_names())
        st = AbstractState("HEOS", names)
        st.set_mole_fractions(composition.coolprop_fractions())
        return st

    # ----- public API ---------------------------------------------------------

    def point_properties(
        self, composition: GasComposition, pressure_mpa: float, temperature_k: float
    ) -> PointPropertiesResult:
        """Full state at (p, T). Raises OutOfRangeError past the hard cutoff (W3.4)."""
        if is_hard_out_of_range(pressure_mpa):
            raise OutOfRangeError(
                f"Pressure {pressure_mpa} MPa is outside the absolute model cutoff "
                "(0 < p <= 35 MPa). Calculation aborted (W3.4).",
                critical=True,
            )
        state = self._resolve_pt(composition, pressure_mpa, temperature_k)
        violations = check_point(pressure_mpa, temperature_k)
        warnings = [v.message for v in violations]
        return PointPropertiesResult(
            state=state,
            is_within_model_range=not violations,
            warnings=warnings,
            out_of_range_groups=[v.group for v in violations],
        )

    def enthalpy_kj_kg(
        self, composition: GasComposition, pressure_mpa: float, temperature_k: float
    ) -> float:
        st = self._state(composition)
        st.update(CP.PT_INPUTS, pressure_mpa * 1e6, temperature_k)
        return st.hmass() / 1000.0

    def temperature_at_ph(
        self,
        composition: GasComposition,
        pressure_mpa: float,
        enthalpy_kj_kg: float,
        t_guess_low: float,
        t_guess_high: float,
    ) -> float:
        """Robust T such that h(p, T) = target, via Brent over PT states."""
        st = self._state(composition)
        p_pa = pressure_mpa * 1e6
        target = enthalpy_kj_kg * 1000.0

        def f(t: float) -> float:
            st.update(CP.PT_INPUTS, p_pa, t)
            return st.hmass() - target

        return self._brent(f, t_guess_low, t_guess_high, "enthalpy")

    def temperature_at_ps(
        self,
        composition: GasComposition,
        pressure_mpa: float,
        entropy_kj_kgk: float,
        t_guess_low: float,
        t_guess_high: float,
    ) -> float:
        """Robust T such that s(p, T) = target (isentropic outlet), via Brent over PT states."""
        st = self._state(composition)
        p_pa = pressure_mpa * 1e6
        target = entropy_kj_kgk * 1000.0

        def f(t: float) -> float:
            st.update(CP.PT_INPUTS, p_pa, t)
            return st.smass() - target

        return self._brent(f, t_guess_low, t_guess_high, "entropy")

    # ----- internals ----------------------------------------------------------

    def _resolve_pt(
        self, composition: GasComposition, pressure_mpa: float, temperature_k: float
    ) -> StatePoint:
        st = self._state(composition)
        try:
            st.update(CP.PT_INPUTS, pressure_mpa * 1e6, temperature_k)
            z = st.p() / (st.rhomolar() * _R * st.T())
            # Joule-Thomson: dT/dP at constant H, in K/Pa -> K/MPa.
            jt_k_per_pa = st.first_partial_deriv(CP.iT, CP.iP, CP.iHmass)
            # Transport properties are not available for every mixture/range; degrade gracefully.
            viscosity, conductivity = self._transport(st)
            return StatePoint(
                pressure_mpa=pressure_mpa,
                temperature_k=temperature_k,
                compressibility_factor=z,
                density_kg_m3=st.rhomass(),
                molar_mass_kg_kmol=st.molar_mass() * 1000.0,
                specific_heat_cp_kj_kgk=st.cpmass() / 1000.0,
                specific_heat_cv_kj_kgk=st.cvmass() / 1000.0,
                enthalpy_kj_kg=st.hmass() / 1000.0,
                entropy_kj_kgk=st.smass() / 1000.0,
                joule_thomson_k_mpa=jt_k_per_pa * 1e6,
                speed_of_sound_m_s=st.speed_sound(),
                viscosity_pa_s=viscosity,
                thermal_conductivity_w_mk=conductivity,
            )
        except Exception as exc:  # noqa: BLE001 — surface CoolProp failures as engine errors
            raise StateSolveError(
                f"Failed to resolve state at p={pressure_mpa} MPa, T={temperature_k} K: {exc}"
            ) from exc

    @staticmethod
    def _transport(st: AbstractState) -> tuple[float | None, float | None]:
        """Return (dynamic viscosity Pa*s, thermal conductivity W/(m*K)) or None if unavailable.

        CoolProp exposes transport properties for many mixtures; where a binary interaction is
        missing it raises. The OPZ §3.2 alternative (Lee-Gonzalez-Eakin viscosity, TRAPP
        conductivity) can replace this without changing the domain contract.
        """
        try:
            viscosity = st.viscosity()
        except Exception:  # noqa: BLE001
            viscosity = None
        try:
            conductivity = st.conductivity()
        except Exception:  # noqa: BLE001
            conductivity = None
        return viscosity, conductivity

    @staticmethod
    def _brent(f, low: float, high: float, what: str) -> float:
        try:
            return brentq(f, low, high, xtol=_BRENT_XTOL)
        except ValueError as exc:
            raise StateSolveError(
                f"Could not bracket {what} solution in [{low}, {high}] K: {exc}"
            ) from exc
