"""Report-based macro scenarios (ARE/KPEiR/Fit-for-55) and anchoring."""

from __future__ import annotations

from egsd.application.price_service import build_report_scenario
from egsd.domain.prices.models import PricePoint, PriceSeries


def _series(current: float) -> PriceSeries:
    return PriceSeries(
        code="EU_ETS_EUA", name="ETS", unit="EUR/t", currency="EUR", source="seed",
        points=[PricePoint("2026-07-13", current)],
    )


def test_anchoring_sets_reference_to_current_price():
    fam = {
        "low": {2026: 78, 2027: 80},
        "base": {2026: 82, 2027: 90},
        "high": {2026: 88, 2027: 100},
    }
    src = {"low": "EU Ref", "base": "ARE", "high": "FF55"}
    rs = build_report_scenario(_series(100.0), fam, src, anchor=True)
    assert rs.reference_value == 100.0
    first = rs.bands[0]
    # All families rescaled so their 2026 value equals the current price.
    assert first.low == first.base == first.high == 100.0
    # Ordering preserved: low <= base <= high in later years.
    later = rs.bands[-1]
    assert later.low <= later.base <= later.high


def test_unanchored_uses_report_values_directly():
    fam = {"low": {2026: 78}, "base": {2026: 82}, "high": {2026: 88}}
    src = {"low": "a", "base": "b", "high": "c"}
    rs = build_report_scenario(_series(100.0), fam, src, anchor=False)
    assert rs.bands[0].base == 82  # report value, not the current price


# ----- API ---------------------------------------------------------------------


def test_macro_scenarios_listed(client):
    r = client.get("/api/v1/prices/scenarios/macro")
    assert r.status_code == 200, r.text
    families = {m["family"] for m in r.json()}
    assert families == {"low", "base", "high"}
    assert all(m["source"] for m in r.json())  # every scenario is attributed


def test_report_scenario_endpoint(client):
    r = client.get("/api/v1/prices/EU_ETS_EUA/report-scenario")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["anchored"] is True
    assert data["referenceValue"] > 0
    assert len(data["sources"]) == 3
    for b in data["bands"]:
        assert b["low"] <= b["base"] <= b["high"]
    # Spans to 2050.
    assert data["bands"][-1]["year"] == 2050
