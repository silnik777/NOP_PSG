"""ISO 6976 combustion properties: calorific value and Wobbe index.

Ideal-gas volumetric basis (real-gas Z-correction is a documented refinement for a later
phase). Component molar calorific values are the ISO 6976 gross/net values at 25 degC
combustion reference. Volumetric values use the ideal molar volume at the *metering*
reference temperature of the chosen combustion/metering pair.
"""

from __future__ import annotations

from ...domain.gas.composition import GasComposition
from ...domain.gas.properties import CombustionResult

_R = 8.314462618  # J/(mol*K)
_P_REF = 101_325.0  # Pa (normal pressure)
_M_AIR = 28.9647  # g/mol (dry air)

# Component gross (Hs) and net (Hi) molar calorific value at 25 degC, kJ/mol; molar mass g/mol.
# Source: ISO 6976 reference tables (standard enthalpies of combustion).
_COMPONENT_DATA: dict[str, tuple[float, float, float]] = {
    # key: (Hs_kJ_mol, Hi_kJ_mol, M_g_mol)  — ISO 6976 reference tables, 25 degC combustion.
    "methane": (890.63, 802.60, 16.043),
    "ethane": (1560.69, 1428.64, 30.070),
    "propane": (2219.17, 2043.11, 44.097),
    "n_butane": (2877.40, 2657.32, 58.123),
    "i_butane": (2869.38, 2649.30, 58.123),
    "n_pentane": (3535.77, 3271.67, 72.150),
    "i_pentane": (3528.83, 3264.73, 72.150),
    "n_hexane": (4194.75, 3886.65, 86.177),
    "n_heptane": (4853.30, 4501.20, 100.204),
    "n_octane": (5511.62, 5115.52, 114.231),
    "hydrogen": (285.83, 241.72, 2.016),
    "carbon_monoxide": (282.98, 282.98, 28.010),
    "hydrogen_sulfide": (562.01, 517.90, 34.081),
    "nitrogen": (0.0, 0.0, 28.014),
    "carbon_dioxide": (0.0, 0.0, 44.010),
    "oxygen": (0.0, 0.0, 31.999),
    "water": (0.0, 0.0, 18.015),
    "argon": (0.0, 0.0, 39.948),
    "helium": (0.0, 0.0, 4.003),
}

# combustion/metering reference pair (degC) -> metering temperature in K.
_REFERENCE_PAIRS: dict[str, float] = {
    "25/0": 273.15,
    "25/15": 288.15,
    "15/15": 288.15,
    "0/0": 273.15,
    "25/20": 293.15,
}


def combustion_properties(
    composition: GasComposition, reference_pair: str = "25/0"
) -> CombustionResult:
    if reference_pair not in _REFERENCE_PAIRS:
        raise ValueError(
            f"Unsupported reference pair {reference_pair!r}; "
            f"choose one of {sorted(_REFERENCE_PAIRS)}."
        )
    metering_t = _REFERENCE_PAIRS[reference_pair]
    molar_volume = _R * metering_t / _P_REF  # m3/mol (ideal)

    hs_molar = 0.0  # kJ/mol
    hi_molar = 0.0
    molar_mass = 0.0  # g/mol
    for key, x in composition.fractions.items():
        hs, hi, m = _COMPONENT_DATA[key]
        hs_molar += x * hs
        hi_molar += x * hi
        molar_mass += x * m

    # Volumetric, MJ/m3:  (kJ/mol) / (m3/mol) / 1000
    hs_vol = hs_molar / molar_volume / 1000.0
    hi_vol = hi_molar / molar_volume / 1000.0
    relative_density = molar_mass / _M_AIR
    wobbe = hs_vol / (relative_density**0.5)

    return CombustionResult(
        reference_pair=reference_pair,
        gross_calorific_value_mj_m3=hs_vol,
        net_calorific_value_mj_m3=hi_vol,
        gross_calorific_value_mj_mol=hs_molar / 1000.0,
        relative_density=relative_density,
        wobbe_index_mj_m3=wobbe,
    )
