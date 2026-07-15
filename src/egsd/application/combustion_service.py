"""CoreCombustionEngine — stoichiometric combustion and process CO2 from fuel composition.

Implements OPZ §27 (Proces spalania) / §28 (Emisje, warstwa CMB): CO2 is derived first from
the fuel's carbon balance (not a single volumetric factor), together with theoretical oxygen
and air demand, wet/dry flue-gas composition, excess air, per-unit emission intensities, and
an explicit fossil/biogenic carbon split (FuelOriginProfile). Every result carries its method
(EMI-CMB-013) so a screening/factor value can never masquerade as a balance result.
"""

from __future__ import annotations

from ..domain.combustion.models import (
    COMPONENT_ATOMS,
    MOLAR_MASS_CO2,
    N2_PER_O2,
    CombustionInput,
    CombustionMethod,
    CombustionResult,
    FlueGas,
)
from ..domain.gas.composition import GasComposition
from ..infrastructure.gas_engine.iso6976 import combustion_properties

_INERT_CARBON = {"carbon_dioxide"}
_O2_MOLE_FRACTION_AIR = 20.95 / 100.0


def _o2_demand(c: int, h: int, o: int, s: int) -> float:
    """Stoichiometric O2 (mol) to fully oxidize one mole of a species (C->CO2, H->H2O,
    S->SO2), crediting oxygen already bound in the molecule."""
    return c + h / 4.0 + s - o / 2.0


def _lambda_from_flue_o2(theoretical_o2: float, dry_const: float, target_frac: float) -> float:
    """Solve excess-air ratio lambda from a target O2 fraction in dry flue gas."""
    # O2_dry(l) = (l-1)*O2th ; dry(l) = dry_const - O2th + l*O2th*(1+N2_PER_O2)
    # target = O2_dry/dry  ->  linear in l.
    o2th = theoretical_o2
    a = o2th - target_frac * o2th * (1.0 + N2_PER_O2)
    b = -o2th - target_frac * (dry_const - o2th)
    if abs(a) < 1e-12:
        return 1.0
    return -b / a


def evaluate(comp: GasComposition, data: CombustionInput) -> CombustionResult:
    frac = comp.fractions
    warnings: list[str] = []

    total_c_combustible = 0.0  # carbon in combustible species (oxidizes to CO2/CO)
    total_c_inert = 0.0  # carbon already present as CO2 (passes through)
    total_h = 0.0
    total_s = 0.0
    fuel_n2 = 0.0
    theoretical_o2 = 0.0
    inert_extra: dict[str, float] = {"argon": 0.0, "helium": 0.0}

    for key, x in frac.items():
        c, h, o, _n, s = _unpack(key)
        total_h += x * h
        total_s += x * s
        if key == "nitrogen":
            fuel_n2 += x  # one N2 molecule per mole
        if key in inert_extra:
            inert_extra[key] += x
        if key in _INERT_CARBON:
            total_c_inert += x * c
        else:
            total_c_combustible += x * c
            theoretical_o2 += x * _o2_demand(c, h, o, s)

    if theoretical_o2 < 0:
        warnings.append(
            "Fuel already contains more oxygen than needed for complete combustion; "
            "theoretical air demand clamped to zero."
        )
        theoretical_o2 = 0.0

    eps = data.carbon_oxidation_factor
    if not 0.0 < eps <= 1.0:
        raise ValueError("carbon_oxidation_factor must be in (0, 1].")
    if eps < 1.0:
        warnings.append(f"Incomplete oxidation assumed (oxidation factor {eps:.3f}); "
                        "unburnt carbon reported as CO in the flue gas.")

    # --- Excess air ---
    theoretical_air = theoretical_o2 / _O2_MOLE_FRACTION_AIR if theoretical_o2 > 0 else 0.0
    co2_from_combustion = eps * total_c_combustible
    co2_passthrough = total_c_inert
    co2_total = co2_from_combustion + co2_passthrough
    co_unburnt = (1.0 - eps) * total_c_combustible
    h2o = total_h / 2.0
    so2 = total_s

    dry_const = (
        co2_total + co_unburnt + so2 + fuel_n2 + inert_extra["argon"] + inert_extra["helium"]
    )
    if data.excess_air_ratio is not None:
        lam = data.excess_air_ratio
    elif data.flue_o2_dry_pct is not None:
        lam = _lambda_from_flue_o2(theoretical_o2, dry_const, data.flue_o2_dry_pct / 100.0)
    else:
        lam = 1.0
    if lam < 1.0:
        warnings.append(f"Excess-air ratio {lam:.3f} < 1 implies sub-stoichiometric combustion.")

    o2_supplied = lam * theoretical_o2
    o2_excess = max(0.0, (lam - 1.0) * theoretical_o2)
    n2_from_air = N2_PER_O2 * o2_supplied

    # --- Flue-gas composition (mol per mol fuel) ---
    wet: dict[str, float] = {}
    dry: dict[str, float] = {}

    def _add(name: str, wet_mol: float, dry_mol: float | None = None) -> None:
        if wet_mol > 1e-15:
            wet[name] = wet.get(name, 0.0) + wet_mol
        d = wet_mol if dry_mol is None else dry_mol
        if d > 1e-15:
            dry[name] = dry.get(name, 0.0) + d

    _add("carbon_dioxide", co2_total)
    _add("carbon_monoxide", co_unburnt)
    _add("sulfur_dioxide", so2)
    _add("nitrogen", fuel_n2 + n2_from_air)
    _add("oxygen", o2_excess)
    _add("argon", inert_extra["argon"])
    _add("helium", inert_extra["helium"])
    _add("water", h2o, dry_mol=0.0)  # water only in the wet basis

    # --- Fossil / biogenic CO2 split (FuelOriginProfile) ---
    bio = data.biogenic_fraction or {}
    for k in bio:
        if not 0.0 <= bio[k] <= 1.0:
            raise ValueError(f"biogenic_fraction[{k!r}] must be in [0, 1].")
    co2_biogenic = 0.0
    for key, x in frac.items():
        c, *_ = _unpack(key)
        if c == 0:
            continue
        carbon = x * c
        if key not in _INERT_CARBON:
            carbon *= eps
        co2_biogenic += carbon * bio.get(key, 0.0)
    co2_fossil = co2_total - co2_biogenic

    # --- Energy / volumetric normalization (ISO 6976 heating value) ---
    props = combustion_properties(comp, data.reference_pair)
    gross_mj_mol = props.gross_calorific_value_mj_mol
    gross_mj_m3 = props.gross_calorific_value_mj_m3
    molar_volume_m3 = gross_mj_mol / gross_mj_m3 if gross_mj_m3 > 0 else None

    co2_kg_per_mol = co2_total * MOLAR_MASS_CO2 / 1000.0
    co2_kg_per_nm3 = co2_kg_per_mol / molar_volume_m3 if molar_volume_m3 else 0.0
    co2_kg_per_gj_input = (
        co2_kg_per_mol * 1000.0 / gross_mj_mol if gross_mj_mol > 0 else 0.0
    )
    co2_kg_per_gj_useful: float | None = None
    if data.useful_efficiency is not None:
        if not 0.0 < data.useful_efficiency <= 1.0:
            raise ValueError("useful_efficiency must be in (0, 1].")
        co2_kg_per_gj_useful = co2_kg_per_gj_input / data.useful_efficiency

    return CombustionResult(
        method=CombustionMethod.STOICHIOMETRIC,
        theoretical_o2_mol_per_mol=theoretical_o2,
        theoretical_air_mol_per_mol=theoretical_air,
        excess_air_ratio=lam,
        co2_total_mol_per_mol=co2_total,
        co2_fossil_mol_per_mol=co2_fossil,
        co2_biogenic_mol_per_mol=co2_biogenic,
        flue_gas=FlueGas(wet=_normalize(wet), dry=_normalize(dry)),
        co2_kg_per_mol_fuel=co2_kg_per_mol,
        co2_kg_per_nm3_fuel=co2_kg_per_nm3,
        co2_kg_per_gj_input=co2_kg_per_gj_input,
        co2_kg_per_gj_useful=co2_kg_per_gj_useful,
        gross_calorific_value_mj_m3=gross_mj_m3,
        warnings=tuple(warnings),
    )


def _unpack(key: str) -> tuple[int, int, int, int, int]:
    atoms = COMPONENT_ATOMS.get(key)
    if atoms is None:
        raise ValueError(f"No atomic formula for component {key!r}.")
    return atoms


def _normalize(mols: dict[str, float]) -> dict[str, float]:
    total = sum(mols.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in mols.items()}
