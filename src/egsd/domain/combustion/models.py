"""Combustion / process-emission domain contracts (OPZ §27 Proces spalania, §28 Emisje).

The platform's CO2 emission from fuel combustion is computed *from the fuel composition and
a carbon balance* (OPZ §27: "Emisje ze spalania (...) muszą być obliczane w pierwszej
kolejności na podstawie procesu spalania, składu paliwa, ilości paliwa i bilansu
pierwiastków"), not from a single volumetric CO2 factor. This module carries the atomic
formulas and the immutable result contract; the arithmetic lives in the application service.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# Atomic formula per canonical component: (nC, nH, nO, nN, nS).
# Used for the element balance (C, H, O, N, S) that drives stoichiometric combustion.
COMPONENT_ATOMS: dict[str, tuple[int, int, int, int, int]] = {
    #                 C  H  O  N  S
    "methane": (1, 4, 0, 0, 0),
    "ethane": (2, 6, 0, 0, 0),
    "propane": (3, 8, 0, 0, 0),
    "n_butane": (4, 10, 0, 0, 0),
    "i_butane": (4, 10, 0, 0, 0),
    "n_pentane": (5, 12, 0, 0, 0),
    "i_pentane": (5, 12, 0, 0, 0),
    "n_hexane": (6, 14, 0, 0, 0),
    "n_heptane": (7, 16, 0, 0, 0),
    "n_octane": (8, 18, 0, 0, 0),
    "hydrogen": (0, 2, 0, 0, 0),
    "carbon_monoxide": (1, 0, 1, 0, 0),
    "hydrogen_sulfide": (0, 2, 0, 0, 1),
    "nitrogen": (0, 0, 0, 2, 0),
    "carbon_dioxide": (1, 0, 2, 0, 0),  # already oxidized — passes through to flue gas
    "oxygen": (0, 0, 2, 0, 0),  # oxidizer already present in the fuel
    "water": (0, 2, 1, 0, 0),  # inert moisture — reports to wet flue gas
    "argon": (0, 0, 0, 0, 0),
    "helium": (0, 0, 0, 0, 0),
}

# Components whose carbon is already fully oxidized in the fuel (does not consume O2).
_INERT_CARBON = {"carbon_dioxide"}

MOLAR_MASS_CO2 = 44.010  # g/mol
_M_AIR = 28.9647  # g/mol dry air
# Dry-air mole ratio: 20.95 % O2, remainder lumped as N2 (incl. argon) -> N2/O2 = 3.7738.
N2_PER_O2 = 79.05 / 20.95


class CombustionMethod(str, Enum):
    """OPZ §27.1 method hierarchy (explicitly reported on every result)."""

    STOICHIOMETRIC = "stoichiometric"  # from fuel composition + carbon balance
    ELEMENT_BALANCE = "element_balance"
    PROCESS_MODEL = "process_model"
    CALORIFIC_FACTOR = "calorific_factor"
    REFERENCE_FACTOR = "reference_factor"
    MEASUREMENT = "measurement"
    MANUFACTURER = "manufacturer"
    SCREENING = "screening"


@dataclass(frozen=True)
class CombustionInput:
    """One combustion calculation for a resolved fuel composition."""

    # Excess-air controls (provide exactly one; lambda takes precedence if both given).
    excess_air_ratio: float | None = None  # lambda = actual air / stoichiometric air (>=1)
    flue_o2_dry_pct: float | None = None  # target O2 in dry flue gas (vol %)
    carbon_oxidation_factor: float = 1.0  # fraction of fuel C oxidized to CO2 (<=1)
    # Optional per-component biogenic carbon fraction (0..1); default = fossil (0).
    biogenic_fraction: dict[str, float] = field(default_factory=dict)
    # Conversion efficiency to useful energy (boiler/engine/CHP), for intensity-per-useful.
    useful_efficiency: float | None = None
    reference_pair: str = "25/0"  # metering pair for volumetric/energy normalization


@dataclass(frozen=True)
class FlueGas:
    """Molar flue-gas composition per mole of fuel (wet and dry bases)."""

    wet: dict[str, float]
    dry: dict[str, float]


@dataclass(frozen=True)
class CombustionResult:
    method: CombustionMethod
    # Air/oxygen demand (mol per mol fuel).
    theoretical_o2_mol_per_mol: float
    theoretical_air_mol_per_mol: float
    excess_air_ratio: float
    # CO2 split (mol per mol fuel).
    co2_total_mol_per_mol: float
    co2_fossil_mol_per_mol: float
    co2_biogenic_mol_per_mol: float
    flue_gas: FlueGas
    # Intensities.
    co2_kg_per_mol_fuel: float
    co2_kg_per_nm3_fuel: float
    co2_kg_per_gj_input: float  # per GJ of gross calorific input
    co2_kg_per_gj_useful: float | None
    gross_calorific_value_mj_m3: float
    warnings: tuple[str, ...] = ()
    result_class: str = "Engineering"
