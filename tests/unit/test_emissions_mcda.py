"""CoreEmissionEngine and MCDA/TOPSIS with Gatekeeper."""

from __future__ import annotations

import pytest

from egsd.application.emission_service import evaluate
from egsd.application.mcda_service import rank
from egsd.domain.emissions.models import EmissionInput
from egsd.domain.mcda.models import (
    GatekeeperError,
    MacroAssumptions,
    VariantScore,
    Weights,
)

# ----- emissions ----------------------------------------------------------------


def test_scope1_methane_uses_ar6_gwp():
    result = evaluate(EmissionInput(methane_leak_tonnes=10.0))
    # 10 t CH4 * 29.8 = 298 t CO2e (AR6, per OPZ W6.2).
    assert result.breakdown.scope1_t_co2e == pytest.approx(298.0)
    assert result.breakdown.scope2_t_co2e == 0.0


def test_hydrogen_leak_counts_as_indirect_ghg():
    result = evaluate(EmissionInput(hydrogen_leak_tonnes=5.0))
    assert result.breakdown.scope1_t_co2e == pytest.approx(55.0)  # 5 * 11


def test_scope2_grid_factor():
    result = evaluate(EmissionInput(grid_electricity_mwh=1000.0))
    assert result.breakdown.scope2_t_co2e == pytest.approx(597.0)  # 1000 MWh * 597 kg/MWh


def test_scope3_gray_vs_green_hydrogen():
    gray = evaluate(EmissionInput(hydrogen_supplied_tonnes=100.0, hydrogen_origin="gray"))
    green = evaluate(EmissionInput(hydrogen_supplied_tonnes=100.0, hydrogen_origin="green"))
    assert gray.breakdown.scope3_t_co2e == pytest.approx(1090.0)
    assert green.breakdown.scope3_t_co2e == pytest.approx(50.0)
    assert gray.breakdown.total_t_co2e > green.breakdown.total_t_co2e


def test_invalid_h2_origin_rejected():
    with pytest.raises(ValueError):
        evaluate(EmissionInput(hydrogen_supplied_tonnes=1.0, hydrogen_origin="pink"))


# ----- MCDA ----------------------------------------------------------------------


def _variant(name, npv, capex, co2e, trl, r=0.06, scen="MACRO-ARE-BASE"):
    return VariantScore(
        name=name, npv=npv, capex=capex, co2e_tonnes=co2e, trl=trl,
        assumptions=MacroAssumptions(
            discount_rate=r, scenario_code=scen, engine_version="gpe-core-1.0.0-heos"
        ),
    )


def test_topsis_prefers_dominating_variant():
    a = _variant("A-dominates", npv=10e6, capex=5e6, co2e=1000, trl=9)
    b = _variant("B-worse", npv=5e6, capex=8e6, co2e=5000, trl=6)
    result = rank([a, b])
    assert result.ranking[0].name == "A-dominates"
    assert result.ranking[0].closeness > result.ranking[1].closeness


def test_weights_normalize_to_one():
    w = Weights(npv=40, capex=20, co2e=25, trl=15).normalized()
    assert w.npv + w.capex + w.co2e + w.trl == pytest.approx(1.0)
    assert w.npv == pytest.approx(0.40)


def test_gatekeeper_blocks_mismatched_discount_rate():
    a = _variant("W1", 10e6, 5e6, 1000, 9, r=0.08)
    b = _variant("W2", 8e6, 6e6, 2000, 8, r=0.065)
    with pytest.raises(GatekeeperError) as exc:
        rank([a, b])
    msg = str(exc.value)
    assert "stopa dyskontowa" in msg
    assert "Zrównaj parametry makroekonomiczne" in msg


def test_gatekeeper_blocks_mismatched_scenario():
    a = _variant("W1", 10e6, 5e6, 1000, 9, scen="MACRO-ARE-BASE")
    b = _variant("W2", 8e6, 6e6, 2000, 8, scen="MACRO-FF55-HIGH")
    with pytest.raises(GatekeeperError):
        rank([a, b])


def test_weight_change_can_flip_ranking():
    # Eco variant: much lower CO2e; Profit variant: higher NPV.
    eco = _variant("Eco", npv=6e6, capex=6e6, co2e=500, trl=8)
    profit = _variant("Profit", npv=12e6, capex=6e6, co2e=9000, trl=8)
    npv_heavy = rank([eco, profit], Weights(npv=0.8, capex=0.05, co2e=0.1, trl=0.05))
    co2_heavy = rank([eco, profit], Weights(npv=0.1, capex=0.05, co2e=0.8, trl=0.05))
    assert npv_heavy.ranking[0].name == "Profit"
    assert co2_heavy.ranking[0].name == "Eco"
