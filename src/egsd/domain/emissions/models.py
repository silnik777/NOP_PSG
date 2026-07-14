"""Emission accounting domain contracts (OPZ §6 — GHG Protocol, GWP AR6)."""

from __future__ import annotations

from dataclasses import dataclass, field

# GWP100 factors per IPCC AR6 (OPZ W6.2). CO2 = 1 by definition; hydrogen is an
# indirect greenhouse gas with GWP100 ~ 11.
GWP100_AR6: dict[str, float] = {
    "co2": 1.0,
    "ch4": 29.8,
    "h2": 11.0,
}


@dataclass(frozen=True)
class EmissionFactors:
    """Versioned emission-factor set (reference data, KOBiZE/URE vintages)."""

    grid_electricity_kg_co2_per_mwh: float = 597.0  # KSE grid factor (KOBiZE-style)
    gas_combustion_kg_co2_per_gj: float = 55.82  # natural-gas combustion (per GJ HHV)
    h2_gray_kg_co2e_per_kg: float = 10.9  # SMR without CCS (Scope 3)
    h2_green_kg_co2e_per_kg: float = 0.5  # electrolysis on renewables (Scope 3)
    vintage: str = "KOBiZE/IPCC AR6 (dane referencyjne)"


@dataclass(frozen=True)
class EmissionInput:
    # Scope 1
    methane_leak_tonnes: float = 0.0  # CH4 released (leaks, vents, emergency outflow)
    hydrogen_leak_tonnes: float = 0.0  # H2 released
    heater_gas_use_gj: float = 0.0  # gas burned in preheaters (GJ, HHV)
    # Scope 2
    grid_electricity_mwh: float = 0.0  # purchased KSE electricity (compressor drives etc.)
    # Scope 3
    hydrogen_supplied_tonnes: float = 0.0  # delivered H2 mass
    hydrogen_origin: str = "gray"  # "gray" | "green"


@dataclass(frozen=True)
class ScopeBreakdown:
    scope1_t_co2e: float
    scope2_t_co2e: float
    scope3_t_co2e: float

    @property
    def total_t_co2e(self) -> float:
        return self.scope1_t_co2e + self.scope2_t_co2e + self.scope3_t_co2e


@dataclass(frozen=True)
class EmissionResult:
    breakdown: ScopeBreakdown
    detail: dict[str, float] = field(default_factory=dict)  # component -> t CO2e
    gwp_source: str = "IPCC AR6 GWP100 (CH4=29.8, H2=11)"
    factors_vintage: str = ""
