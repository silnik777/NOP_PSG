"""CoreFinanceEngine: NPV, IRR, LCO and sensitivity."""

from __future__ import annotations

import pytest

from egsd.application.finance_service import evaluate, irr, npv, sensitivity
from egsd.domain.finance.models import DcfInput, LcoKind


def test_npv_known_value():
    # -100 now, +60 and +60 at years 1,2 at 10%.
    flows = [-100.0, 60.0, 60.0]
    assert npv(0.10, flows) == pytest.approx(-100 + 60 / 1.1 + 60 / 1.21, rel=1e-9)


def test_irr_conventional():
    rate, warn = irr([-100.0, 60.0, 60.0])
    assert warn is None
    assert rate == pytest.approx(0.1306, abs=1e-3)


def test_irr_flags_non_conventional():
    rate, warn = irr([-100.0, 300.0, -200.0])  # two sign changes
    assert rate is None
    assert "Non-conventional" in warn


def test_irr_no_sign_change():
    rate, warn = irr([-100.0, -10.0, -10.0])
    assert rate is None
    assert warn is not None


def test_evaluate_with_lcoe():
    data = DcfInput(
        capex=15_000_000, discount_rate=0.08, horizon_years=10,
        opex_per_year=[300_000] * 10, revenue_per_year=[5_000_000] * 10,
        output_per_year=[20_000] * 10,
    )
    result = evaluate(data, LcoKind.LCOE)
    assert result.npv > 0
    assert result.irr is not None and result.irr > 0.08
    assert result.lco_value is not None and result.lco_value > 0
    assert result.lco_kind == "LCOE"
    assert len(result.net_cash_flows) == 11  # year 0..10


def test_sensitivity_has_four_axes_and_symmetric_steps():
    data = DcfInput(
        capex=10_000_000, discount_rate=0.08, horizon_years=10,
        opex_per_year=[200_000] * 10, energy_cost_per_year=[1_000_000] * 10,
        revenue_per_year=[3_000_000] * 10,
    )
    tornado = sensitivity(data)
    assert {a.parameter for a in tornado.axes} == {
        "capex", "energy_cost", "revenue", "discount_rate"
    }
    capex_axis = next(a for a in tornado.axes if a.parameter == "capex")
    assert [p.delta_pct for p in capex_axis.points][0] == -30
    assert [p.delta_pct for p in capex_axis.points][-1] == 30
    # Higher CAPEX lowers NPV.
    npv_low = next(p.npv for p in capex_axis.points if p.delta_pct == -30)
    npv_high = next(p.npv for p in capex_axis.points if p.delta_pct == 30)
    assert npv_low > npv_high
