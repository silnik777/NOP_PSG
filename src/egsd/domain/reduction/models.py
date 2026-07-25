"""Module III — pressure reduction & energy management (MRC) domain contracts.

Karta Modułu III: isenthalpic throttling (Joule-Thomson) at reduction stations with
hydrate/ground-freezing guard and preheater sizing, versus a turbo-expander alternative
recovering shaft power. The p-T path is reported against the mixture dew line
(phase envelope from the GasPropertyEngine) to show the two-phase safety margin.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..gas.composition import GasComposition
from ..thermo.compression import ResultClass

# Hydrate / ground-freezing guard at station outlet (OPZ Module III business problem).
HYDRATE_GUARD_K = 273.15
DEFAULT_OUTLET_MARGIN_K = 5.0  # keep outlet at least this far above the guard


@dataclass(frozen=True)
class ReductionInput:
    composition: GasComposition
    mass_flow_kg_s: float
    inlet_pressure_mpa: float
    inlet_temperature_k: float
    outlet_pressure_mpa: float
    min_outlet_temperature_k: float = HYDRATE_GUARD_K + DEFAULT_OUTLET_MARGIN_K
    expander_isentropic_efficiency: float = 0.85  # EXP-TURBO nominal; see /devices

    def __post_init__(self) -> None:
        if self.outlet_pressure_mpa >= self.inlet_pressure_mpa:
            raise ValueError("outlet pressure must be below inlet pressure for reduction.")
        if self.mass_flow_kg_s <= 0:
            raise ValueError("mass flow must be positive.")
        if not 0.0 < self.expander_isentropic_efficiency <= 1.0:
            raise ValueError("expander efficiency must be in (0, 1].")


@dataclass(frozen=True)
class ThrottleResult:
    """Isenthalpic (h = const) valve throttling."""

    outlet_temperature_k: float
    temperature_drop_k: float
    preheat_required: bool
    preheat_inlet_temperature_k: float | None  # inlet T needed to hit the outlet guard
    preheater_duty_kw: float | None


@dataclass(frozen=True)
class ExpanderAlternative:
    """Isentropic-efficiency expansion with shaft-power recovery."""

    recovered_power_kw: float
    outlet_temperature_k: float  # without preheat
    preheat_required: bool
    preheat_inlet_temperature_k: float | None
    preheater_duty_kw: float | None
    net_energy_note: str = ""


@dataclass(frozen=True)
class PtPathPoint:
    pressure_mpa: float
    temperature_k: float
    dew_temperature_k: float | None  # dew line at this pressure (None above cricondenbar)
    margin_k: float | None  # T - T_dew; positive = safely in gas phase


@dataclass(frozen=True)
class ReductionResult:
    throttle: ThrottleResult
    expander: ExpanderAlternative
    pt_path: list[PtPathPoint]
    phase_envelope_available: bool
    result_class: ResultClass = ResultClass.ENGINEERING
    warnings: tuple[str, ...] = field(default_factory=tuple)
