"""Unit tests for the merit-order engine (OPZ §29, BEN-MER)."""

from __future__ import annotations

import pytest

from egsd.application.merit_order_service import build_merit_order
from egsd.domain.meritorder.models import (
    MeritOrderGatekeeperError,
    MeritOrderTechnology,
    Product,
)


def _elec(tech_id, eff, fuel=0.0, ef=0.0, co2=0.0, vopex=0.0, quality="literature"):
    return MeritOrderTechnology(
        tech_id=tech_id, name=tech_id, product=Product.ELECTRICITY,
        functional_unit="MWh_e", efficiency=eff, fuel_price_per_mwh=fuel,
        emission_factor_t_per_mwh_fuel=ef, co2_price_per_t=co2,
        variable_opex_per_mwh=vopex, data_quality=quality,
    )


def test_ranks_by_marginal_cost_ascending():
    techs = [
        _elec("OCGT", 0.38, fuel=120, ef=0.202, co2=350, vopex=5),
        _elec("CCGT", 0.58, fuel=120, ef=0.202, co2=350, vopex=8),
    ]
    res = build_merit_order(techs, Product.ELECTRICITY)
    assert [r.tech_id for r in res.ranking] == ["CCGT", "OCGT"]
    assert res.ranking[0].rank == 1


def test_decomposition_components_sum_to_total():
    res = build_merit_order([_elec("CCGT", 0.58, fuel=120, ef=0.202, co2=350, vopex=8)],
                            Product.ELECTRICITY)
    d = res.ranking[0].decomposition
    assert d.fuel == pytest.approx(120 / 0.58, rel=1e-9)
    assert d.emission == pytest.approx(0.202 / 0.58 * 350, rel=1e-9)
    assert d.varopex == pytest.approx(8.0, rel=1e-9)
    assert res.ranking[0].marginal_cost == pytest.approx(d.total, rel=1e-9)


def test_cost_boundary_excludes_emission():
    tech = _elec("CCGT", 0.58, fuel=120, ef=0.202, co2=350, vopex=8)
    with_emis = build_merit_order([tech], Product.ELECTRICITY).ranking[0].marginal_cost
    no_emis = build_merit_order(
        [tech], Product.ELECTRICITY, cost_boundary=("fuel", "varopex")
    ).ranking[0].marginal_cost
    assert no_emis < with_emis


def test_negative_marginal_cost_preserved():
    # Pressure-reduction energy recovery modeled as an avoided-cost credit.
    res = build_merit_order([_elec("TEX", 1.0, vopex=-15.0, quality="family")],
                            Product.ELECTRICITY)
    assert res.ranking[0].marginal_cost == pytest.approx(-15.0, rel=1e-9)
    assert any("ujemny" in n for n in res.notes)


def test_gatekeeper_blocks_mixed_functional_units():
    techs = [
        _elec("A", 0.5, vopex=10),
        MeritOrderTechnology("B", "B", Product.ELECTRICITY, "GJ_e", 0.5, variable_opex_per_mwh=10),
    ]
    with pytest.raises(MeritOrderGatekeeperError):
        build_merit_order(techs, Product.ELECTRICITY)


def test_metadata_has_provenance_and_checksum():
    res = build_merit_order([_elec("CCGT", 0.58, vopex=8)], Product.ELECTRICITY,
                            metadata={"scenario": "MACRO-BASE"})
    assert res.metadata["scenario"] == "MACRO-BASE"
    assert res.metadata["configChecksum"].startswith("sha256:")
    assert "computedAt" in res.metadata


def test_checksum_is_deterministic_for_same_inputs():
    a = build_merit_order([_elec("CCGT", 0.58, vopex=8)], Product.ELECTRICITY,
                          metadata={"computedAt": "fixed"})
    b = build_merit_order([_elec("CCGT", 0.58, vopex=8)], Product.ELECTRICITY,
                          metadata={"computedAt": "fixed"})
    assert a.metadata["configChecksum"] == b.metadata["configChecksum"]


def test_heat_product_isolated_from_electricity():
    techs = [
        _elec("CCGT", 0.58, vopex=8),
        MeritOrderTechnology("BOIL", "Kocioł", Product.HEAT, "GJ_th", 0.92,
                             fuel_price_per_mwh=120, variable_opex_per_mwh=2),
    ]
    res = build_merit_order(techs, Product.HEAT)
    assert [r.tech_id for r in res.ranking] == ["BOIL"]
    assert res.product is Product.HEAT
