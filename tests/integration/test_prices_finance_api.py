"""Prices and finance API."""

from __future__ import annotations


def test_list_prices_with_current(client):
    r = client.get("/api/v1/prices")
    assert r.status_code == 200, r.text
    codes = {s["code"] for s in r.json()}
    assert {"PL_GAS_TGE", "PL_POWER_TGE", "EU_ETS_EUA"} <= codes
    ets = next(s for s in r.json() if s["code"] == "EU_ETS_EUA")
    assert ets["current"]["value"] > 0
    assert ets["unit"] == "EUR/t"


def test_history_window(client):
    r = client.get("/api/v1/prices/PL_GAS_TGE/history?weeks=12")
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["points"]) == 12
    assert data["current"]["value"] > 0


def test_trend(client):
    r = client.get("/api/v1/prices/EU_ETS_EUA/trend")
    assert r.status_code == 200
    assert "annualizedReturn" in r.json()
    assert "annualizedVolatility" in r.json()


def test_scenario_bands(client):
    r = client.get("/api/v1/prices/PL_POWER_TGE/scenario?startYear=2026&horizon=5")
    assert r.status_code == 200, r.text
    bands = r.json()["bands"]
    assert len(bands) == 6  # year 0..5
    for b in bands:
        assert b["low"] <= b["base"] <= b["high"]


def test_chart_svg(client):
    r = client.get("/api/v1/prices/PL_GAS_TGE/chart.svg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert r.text.startswith("<svg") and r.text.rstrip().endswith("</svg>")


def test_unknown_series_404(client):
    assert client.get("/api/v1/prices/NOPE/history").status_code == 404


def test_dcf_endpoint(client):
    body = {
        "capex": 15000000, "discountRate": 0.08, "horizonYears": 10,
        "opexPerYear": [300000] * 10, "revenuePerYear": [5000000] * 10,
        "outputPerYear": [20000] * 10, "lcoKind": "LCOE",
    }
    r = client.post("/api/v1/finance/dcf", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["npv"] > 0
    assert data["irr"] > 0.08
    assert data["lcoValue"] > 0
    assert data["lcoKind"] == "LCOE"


def test_sensitivity_endpoint(client):
    body = {
        "capex": 10000000, "discountRate": 0.08, "horizonYears": 10,
        "opexPerYear": [200000] * 10, "energyCostPerYear": [1000000] * 10,
        "revenuePerYear": [3000000] * 10,
    }
    r = client.post("/api/v1/finance/sensitivity", json=body)
    assert r.status_code == 200, r.text
    axes = {a["parameter"] for a in r.json()["axes"]}
    assert "capex" in axes and "revenue" in axes
