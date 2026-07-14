"""CoreEmissionEngine — GHG Protocol Scope 1/2/3 with AR6 GWP conversion (OPZ §6).

Single emission standard for the platform; process modules feed physical quantities
(leaked CH4/H2 from the emergency-outflow module, heater fuel, compressor electricity)
and receive a CO2e breakdown. No local emission maths in process modules.
"""

from __future__ import annotations

from ..domain.emissions.models import (
    GWP100_AR6,
    EmissionFactors,
    EmissionInput,
    EmissionResult,
    ScopeBreakdown,
)


def evaluate(data: EmissionInput, factors: EmissionFactors | None = None) -> EmissionResult:
    f = factors or EmissionFactors()

    # Scope 1 — direct: fugitive/vented gas (CH4, H2) + heater combustion CO2.
    leak_ch4 = data.methane_leak_tonnes * GWP100_AR6["ch4"]
    leak_h2 = data.hydrogen_leak_tonnes * GWP100_AR6["h2"]
    heater = data.heater_gas_use_gj * f.gas_combustion_kg_co2_per_gj / 1000.0
    scope1 = leak_ch4 + leak_h2 + heater

    # Scope 2 — purchased grid electricity.
    scope2 = data.grid_electricity_mwh * f.grid_electricity_kg_co2_per_mwh / 1000.0

    # Scope 3 — upstream footprint of delivered hydrogen (gray vs green).
    if data.hydrogen_origin not in ("gray", "green"):
        raise ValueError(f"hydrogen_origin must be 'gray' or 'green', got {data.hydrogen_origin!r}")
    per_kg = f.h2_gray_kg_co2e_per_kg if data.hydrogen_origin == "gray" else (
        f.h2_green_kg_co2e_per_kg
    )
    scope3 = data.hydrogen_supplied_tonnes * 1000.0 * per_kg / 1000.0

    return EmissionResult(
        breakdown=ScopeBreakdown(
            scope1_t_co2e=scope1, scope2_t_co2e=scope2, scope3_t_co2e=scope3
        ),
        detail={
            "scope1_methane_leaks": leak_ch4,
            "scope1_hydrogen_leaks": leak_h2,
            "scope1_heater_combustion": heater,
            "scope2_grid_electricity": scope2,
            "scope3_hydrogen_supply": scope3,
        },
        factors_vintage=f.vintage,
    )
