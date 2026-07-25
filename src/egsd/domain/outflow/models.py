"""Module IV — emergency gas outflow (blowdown) domain contracts.

Karta Modułu IV: choked (critical) and subcritical orifice outflow with lumped-parameter
depressurization of the pipeline inventory. Strict scope: no 3D dispersion/CFD, no VCE/BLEVE
(explicitly excluded by the OPZ; PHAST-class integrations are an optional extra).

KPIs: total released mass per greenhouse component (CH4, H2) [t] and time to reach
atmospheric pressure [min].
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..gas.composition import GasComposition
from ..thermo.compression import ResultClass

ATMOSPHERIC_PRESSURE_MPA = 0.101325


@dataclass(frozen=True)
class BlowdownInput:
    composition: GasComposition
    initial_pressure_mpa: float
    gas_temperature_k: float  # isothermal assumption (conservative for mass)
    orifice_diameter_m: float  # hole / rupture equivalent diameter
    discharge_coefficient: float = 0.62  # sharp-edged orifice default
    # Inventory: either give volume directly, or pipe geometry.
    volume_m3: float | None = None
    pipe_diameter_m: float | None = None
    pipe_length_m: float | None = None
    ambient_pressure_mpa: float = ATMOSPHERIC_PRESSURE_MPA
    max_duration_h: float = 48.0

    def inventory_volume_m3(self) -> float:
        if self.volume_m3 is not None:
            if self.volume_m3 <= 0:
                raise ValueError("volume must be positive.")
            return self.volume_m3
        if self.pipe_diameter_m and self.pipe_length_m:
            return math.pi * self.pipe_diameter_m**2 / 4.0 * self.pipe_length_m
        raise ValueError("provide volume_m3 or pipe_diameter_m + pipe_length_m.")

    def __post_init__(self) -> None:
        if self.initial_pressure_mpa <= self.ambient_pressure_mpa:
            raise ValueError("initial pressure must exceed ambient pressure.")
        if self.orifice_diameter_m <= 0:
            raise ValueError("orifice diameter must be positive.")
        if not 0.0 < self.discharge_coefficient <= 1.0:
            raise ValueError("discharge coefficient must be in (0, 1].")
        self.inventory_volume_m3()  # validate inventory definition eagerly


@dataclass(frozen=True)
class BlowdownProfilePoint:
    time_min: float
    pressure_mpa: float
    mass_flow_kg_s: float
    choked: bool


@dataclass(frozen=True)
class BlowdownResult:
    total_released_tonnes: float
    released_by_component_tonnes: dict[str, float]  # canonical component -> tonnes
    methane_released_tonnes: float
    hydrogen_released_tonnes: float
    co2e_scope1_tonnes: float  # from CoreEmissionEngine (AR6)
    time_to_atmospheric_min: float | None  # None = not reached within max duration
    initial_inventory_tonnes: float
    residual_inventory_tonnes: float
    peak_mass_flow_kg_s: float
    profile: list[BlowdownProfilePoint]
    result_class: ResultClass = ResultClass.ENGINEERING
    warnings: tuple[str, ...] = field(default_factory=tuple)
