"""Unit tests for the stoichiometric combustion engine (OPZ §27, EMI-CMB)."""

from __future__ import annotations

import math

import pytest

from egsd.application import combustion_service as cs
from egsd.domain.combustion.models import CombustionInput, CombustionMethod
from egsd.domain.gas.composition import GasComposition


def _methane() -> GasComposition:
    return GasComposition.from_mapping({"methane": 1.0})


def test_methane_stoichiometry_matches_textbook():
    r = cs.evaluate(_methane(), CombustionInput())
    # CH4 + 2 O2 -> CO2 + 2 H2O
    assert r.theoretical_o2_mol_per_mol == pytest.approx(2.0, rel=1e-9)
    assert r.co2_total_mol_per_mol == pytest.approx(1.0, rel=1e-9)
    # Classic dry-flue CO2 for stoichiometric methane ~ 11.7 %.
    assert r.flue_gas.dry["carbon_dioxide"] == pytest.approx(0.117, abs=0.002)
    # CO2 intensity of pure methane (HHV) ~ 49-50 kg/GJ.
    assert 48.0 < r.co2_kg_per_gj_input < 51.0
    assert r.method is CombustionMethod.STOICHIOMETRIC


def test_air_demand_uses_oxygen_in_fuel():
    # Adding oxygen to the fuel lowers the external O2 demand.
    with_o2 = cs.evaluate(
        GasComposition.from_mapping({"methane": 0.9, "oxygen": 0.1}), CombustionInput()
    )
    pure = cs.evaluate(_methane(), CombustionInput())
    assert with_o2.theoretical_o2_mol_per_mol < 0.9 * pure.theoretical_o2_mol_per_mol


def test_excess_air_from_target_flue_o2():
    r = cs.evaluate(_methane(), CombustionInput(flue_o2_dry_pct=3.0))
    assert r.excess_air_ratio > 1.0
    # The realized dry-flue O2 should recover the 3 % target.
    assert r.flue_gas.dry["oxygen"] == pytest.approx(0.03, abs=1e-3)


def test_biogenic_split_conserves_total_co2():
    comp = GasComposition.from_mapping(
        {"methane": 0.8, "carbon_dioxide": 0.2}
    )
    r = cs.evaluate(comp, CombustionInput(biogenic_fraction={"methane": 1.0}))
    assert r.co2_fossil_mol_per_mol + r.co2_biogenic_mol_per_mol == pytest.approx(
        r.co2_total_mol_per_mol, rel=1e-9
    )
    # Only methane carbon is biogenic; the fuel CO2 carbon stays fossil.
    assert r.co2_biogenic_mol_per_mol == pytest.approx(0.8, rel=1e-9)
    assert r.co2_fossil_mol_per_mol == pytest.approx(0.2, rel=1e-9)


def test_incomplete_oxidation_reports_co_and_warns():
    r = cs.evaluate(_methane(), CombustionInput(carbon_oxidation_factor=0.95))
    assert r.co2_total_mol_per_mol == pytest.approx(0.95, rel=1e-9)
    assert r.flue_gas.wet.get("carbon_monoxide", 0.0) > 0.0
    assert any("oxidation" in w for w in r.warnings)


def test_useful_intensity_scales_with_efficiency():
    r = cs.evaluate(_methane(), CombustionInput(useful_efficiency=0.5))
    assert r.co2_kg_per_gj_useful == pytest.approx(2.0 * r.co2_kg_per_gj_input, rel=1e-9)


def test_adding_propane_raises_co2_intensity():
    base = cs.evaluate(_methane(), CombustionInput())
    enriched = cs.evaluate(
        GasComposition.from_mapping({"methane": 0.9, "propane": 0.1}), CombustionInput()
    )
    # Propane has more carbon per unit energy is only slightly higher; per Nm3 it is clearly higher.
    assert enriched.co2_kg_per_nm3_fuel > base.co2_kg_per_nm3_fuel
    assert enriched.co2_total_mol_per_mol > base.co2_total_mol_per_mol


def test_rejects_bad_oxidation_factor():
    with pytest.raises(ValueError):
        cs.evaluate(_methane(), CombustionInput(carbon_oxidation_factor=1.5))


def test_water_only_in_wet_basis():
    r = cs.evaluate(_methane(), CombustionInput())
    assert "water" in r.flue_gas.wet
    assert "water" not in r.flue_gas.dry
    assert math.isclose(sum(r.flue_gas.dry.values()), 1.0, rel_tol=1e-9)
