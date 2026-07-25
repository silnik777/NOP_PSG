"""Module I — thermodynamic-process (compression) domain contracts.

Mirrors the Karta Modułu I input/output contract from the OPZ. The result class
classifies the calculation as ENGINEERING (real-fluid GERG-2008 states), addressing
risk R-04 (screening vs engineering must be explicit).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..gas.composition import GasComposition


class ResultClass(str, Enum):
    SCREENING = "Screening"
    ENGINEERING = "Engineering"


class ValidationStatus(str, Enum):
    VALID_WITHIN_BOUNDS = "VALID_WITHIN_BOUNDS"
    VALID_WITH_WARNINGS = "VALID_WITH_WARNINGS"
    OUT_OF_BOUNDS = "OUT_OF_BOUNDS"


@dataclass(frozen=True)
class CompressionInput:
    composition: GasComposition
    mass_flow_kg_s: float
    inlet_pressure_mpa: float
    inlet_temperature_k: float
    outlet_pressure_mpa: float
    isentropic_efficiency: float  # eta_iz, fraction (0, 1]
    mechanical_efficiency: float = 1.0  # eta_mech, fraction (0, 1]

    def __post_init__(self) -> None:
        if not 0.0 < self.isentropic_efficiency <= 1.0:
            raise ValueError("isentropic_efficiency must be in (0, 1].")
        if not 0.0 < self.mechanical_efficiency <= 1.0:
            raise ValueError("mechanical_efficiency must be in (0, 1].")
        if self.outlet_pressure_mpa <= self.inlet_pressure_mpa:
            raise ValueError("outlet pressure must exceed inlet pressure for compression.")
        if self.mass_flow_kg_s <= 0:
            raise ValueError("mass flow must be positive.")


@dataclass(frozen=True)
class CompressionResult:
    required_shaft_power_kw: float
    outlet_temperature_k: float
    polytropic_head_kj_kg: float
    isentropic_head_kj_kg: float
    validation_status: ValidationStatus
    result_class: ResultClass = ResultClass.ENGINEERING
    warnings: tuple[str, ...] = ()
