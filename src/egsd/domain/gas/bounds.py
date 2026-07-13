"""Model applicability bounds and property definitions (OPZ §3.2).

Each property group carries a validity envelope in (pressure, temperature). Out-of-range
requests must be rejected hard (rule W3.4) rather than silently extrapolated.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PropertyGroup(str, Enum):
    THERMODYNAMIC_DENSITY = "thermodynamic_density"  # rho, Z
    THERMODYNAMIC_ENERGY = "thermodynamic_energy"  # h, s, Cp, Cv
    JOULE_THOMSON = "joule_thomson"  # mu_JT
    TRANSPORT_VISCOSITY = "transport_viscosity"
    TRANSPORT_CONDUCTIVITY = "transport_conductivity"


@dataclass(frozen=True)
class Envelope:
    p_max_mpa: float
    t_min_k: float
    t_max_k: float
    tolerance_note: str

    def contains(self, p_mpa: float, t_k: float) -> bool:
        return 0.0 < p_mpa <= self.p_max_mpa and self.t_min_k <= t_k <= self.t_max_k


# OPZ §3.2 — property/model/range/tolerance matrix (GERG-2008 working ranges).
ENVELOPES: dict[PropertyGroup, Envelope] = {
    PropertyGroup.THERMODYNAMIC_DENSITY: Envelope(30.0, 60.0, 450.0, "<= 0.1% vs NIST REFPROP"),
    PropertyGroup.THERMODYNAMIC_ENERGY: Envelope(12.0, 100.0, 350.0, "<= 0.5%"),
    PropertyGroup.JOULE_THOMSON: Envelope(10.0, 250.0, 320.0, "<= 1.0%"),
    PropertyGroup.TRANSPORT_VISCOSITY: Envelope(10.0, 260.0, 330.0, "<= 2.0%"),
    PropertyGroup.TRANSPORT_CONDUCTIVITY: Envelope(10.0, 250.0, 350.0, "<= 3.0%"),
}

# Absolute hard cutoff (W3.4): beyond this, computation is aborted with a critical flag.
ABSOLUTE_MAX_PRESSURE_MPA = 35.0


@dataclass(frozen=True)
class RangeViolation:
    group: PropertyGroup
    p_mpa: float
    t_k: float
    envelope: Envelope

    @property
    def message(self) -> str:
        return (
            f"{self.group.value}: point (p={self.p_mpa:.3f} MPa, T={self.t_k:.2f} K) is outside "
            f"the model validity range (p<= {self.envelope.p_max_mpa} MPa, "
            f"{self.envelope.t_min_k}-{self.envelope.t_max_k} K; "
            f"tol {self.envelope.tolerance_note})."
        )


def check_point(p_mpa: float, t_k: float) -> list[RangeViolation]:
    """Return the list of property groups whose validity envelope excludes this (p, T)."""
    return [
        RangeViolation(group, p_mpa, t_k, env)
        for group, env in ENVELOPES.items()
        if not env.contains(p_mpa, t_k)
    ]


def is_hard_out_of_range(p_mpa: float) -> bool:
    """W3.4 critical cutoff — abort immediately and log with a critical flag."""
    return p_mpa <= 0.0 or p_mpa > ABSOLUTE_MAX_PRESSURE_MPA
