"""Energy-storage domain contracts: CAES (compressed air) alongside pipeline linepack.

CAES round-trip energy is a screening-level estimate (adiabatic compression/expansion with
isentropic efficiencies, no reheat/TES modelling). Stored mass and pressures are engineering
values. Diabatic CAES fuel firing and adiabatic thermal storage are out of scope here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..gas.composition import GasComposition
from ..thermo.compression import ResultClass

# Standard dry-air composition (mole fractions) for the CAES working fluid.
AIR_FRACTIONS: dict[str, float] = {"nitrogen": 0.7812, "oxygen": 0.2096, "argon": 0.0092}


def air_composition() -> GasComposition:
    return GasComposition.from_mapping(AIR_FRACTIONS)


@dataclass(frozen=True)
class CaesInput:
    cavern_volume_m3: float
    max_pressure_mpa: float
    min_pressure_mpa: float
    storage_temperature_k: float = 313.15  # ~40 degC cavern
    ambient_pressure_mpa: float = 0.101325
    ambient_temperature_k: float = 288.15
    charge_isentropic_efficiency: float = 0.80
    discharge_isentropic_efficiency: float = 0.85
    compression_stages: int = 3  # intercooled charge train
    expansion_stages: int = 3  # reheated discharge train (adiabatic CAES / TES)
    composition: GasComposition = field(default_factory=air_composition)

    def __post_init__(self) -> None:
        if self.cavern_volume_m3 <= 0:
            raise ValueError("cavern volume must be positive.")
        if not self.ambient_pressure_mpa < self.min_pressure_mpa < self.max_pressure_mpa:
            raise ValueError("require ambient < min_pressure < max_pressure.")
        for eta in (self.charge_isentropic_efficiency, self.discharge_isentropic_efficiency):
            if not 0.0 < eta <= 1.0:
                raise ValueError("efficiencies must be in (0, 1].")
        if self.compression_stages < 1 or self.expansion_stages < 1:
            raise ValueError("stage counts must be >= 1.")


@dataclass(frozen=True)
class CaesResult:
    stored_air_mass_max_tonnes: float  # at max pressure
    working_air_mass_tonnes: float  # deliverable between max and min pressure
    charge_energy_mwh: float  # electricity consumed to charge working mass
    discharge_energy_mwh: float  # electricity delivered on discharge (no reheat)
    round_trip_efficiency: float
    discharge_outlet_temperature_k: float  # turbine outlet (illustrates reheat need)
    result_class: ResultClass = ResultClass.SCREENING
    warnings: tuple[str, ...] = ()
