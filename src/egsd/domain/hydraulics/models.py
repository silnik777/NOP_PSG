"""Module II — hydraulics, transport and linepack (MHT) domain contracts.

Single-segment, steady-state, isothermal compressible gas flow (Karta Modułu II).
Network (looped) solving is explicitly out of scope for this increment (verification
finding #3). The flow reference base is pinned explicitly (verification finding #4).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..gas.composition import GasComposition
from ..thermo.compression import ResultClass, ValidationStatus

# Pinned normal reference conditions for volumetric flow (Nm3): 0 degC, 101.325 kPa.
NORMAL_TEMPERATURE_K = 273.15
NORMAL_PRESSURE_PA = 101_325.0

# OPZ Karta Modułu II validity ranges.
DIAMETER_RANGE_M = (0.05, 1.2)
ROUGHNESS_RANGE_M = (1e-6, 5e-4)  # 0.001 mm .. 0.5 mm


class FlowRegime(str, Enum):
    LAMINAR = "Laminar"  # Re < 2300
    TRANSITIONAL = "Transitional"  # 2300 <= Re < 4000
    TURBULENT = "Turbulent"  # Re >= 4000


@dataclass(frozen=True)
class HydraulicsInput:
    composition: GasComposition
    diameter_m: float  # internal diameter D
    roughness_m: float  # absolute roughness k
    length_m: float  # segment length L
    inlet_pressure_mpa: float
    gas_temperature_k: float  # isothermal flow temperature
    normal_flow_nm3_h: float  # volumetric flow at normal conditions (Nm3/h)

    def __post_init__(self) -> None:
        lo, hi = DIAMETER_RANGE_M
        if not lo <= self.diameter_m <= hi:
            raise ValueError(f"diameter {self.diameter_m} m outside [{lo}, {hi}] m.")
        rlo, rhi = ROUGHNESS_RANGE_M
        if not rlo <= self.roughness_m <= rhi:
            raise ValueError(f"roughness {self.roughness_m} m outside [{rlo}, {rhi}] m.")
        if self.length_m <= 0:
            raise ValueError("length must be positive.")
        if self.normal_flow_nm3_h <= 0:
            raise ValueError("normal flow must be positive.")


@dataclass(frozen=True)
class HydraulicsResult:
    outlet_pressure_mpa: float
    pressure_drop_mpa: float
    mass_flow_kg_s: float
    average_velocity_m_s: float
    reynolds_number: float
    friction_factor: float  # Darcy lambda
    flow_regime: FlowRegime
    mach_number: float
    validation_status: ValidationStatus
    result_class: ResultClass = ResultClass.ENGINEERING
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class LinepackResult:
    linepack_mass_tonnes: float
    linepack_normal_volume_nm3: float
    average_pressure_mpa: float
    average_density_kg_m3: float
