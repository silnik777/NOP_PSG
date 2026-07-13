"""Domain result types for gas-property calculations."""

from __future__ import annotations

from dataclasses import dataclass, field

from .bounds import PropertyGroup


@dataclass(frozen=True)
class StatePoint:
    """A fully-resolved thermodynamic state of a mixture at (p, T)."""

    pressure_mpa: float
    temperature_k: float
    compressibility_factor: float  # Z [-]
    density_kg_m3: float
    molar_mass_kg_kmol: float
    specific_heat_cp_kj_kgk: float
    specific_heat_cv_kj_kgk: float
    enthalpy_kj_kg: float
    entropy_kj_kgk: float
    joule_thomson_k_mpa: float
    speed_of_sound_m_s: float
    # Transport properties may be unavailable for some mixtures (None + warning).
    viscosity_pa_s: float | None = None
    thermal_conductivity_w_mk: float | None = None


@dataclass(frozen=True)
class PointPropertiesResult:
    state: StatePoint
    is_within_model_range: bool
    warnings: list[str] = field(default_factory=list)
    out_of_range_groups: list[PropertyGroup] = field(default_factory=list)


@dataclass(frozen=True)
class CombustionResult:
    """ISO 6976 combustion properties at the chosen reference-condition pair."""

    reference_pair: str  # e.g. "25/0" (combustion/metering, degC)
    gross_calorific_value_mj_m3: float  # superior / HHV, volumetric
    net_calorific_value_mj_m3: float  # inferior / LHV, volumetric
    gross_calorific_value_mj_mol: float
    relative_density: float  # vs dry air
    wobbe_index_mj_m3: float  # superior Wobbe
