"""API tests for start-point modes, combined forecast and forecast chart (§30, PRC)."""

from __future__ import annotations

CODE = "PL_GAS_TGE"


def test_start_point_current_reports_observations(client):
    r = client.post(f"/api/v1/prices/{CODE}/start-point",
                    json={"mode": "current", "windowDays": 30, "aggregation": "mean"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["windowDays"] == 30
    assert 0 < d["observationsUsed"] < 30  # 30 days != 30 observations
    assert any("30 dni" in w for w in d["warnings"])


def test_start_point_user_date(client):
    r = client.post(f"/api/v1/prices/{CODE}/start-point",
                    json={"mode": "user_date", "referenceDate": "2026-05-15", "windowDays": 30})
    assert r.status_code == 200, r.text
    assert r.json()["referenceDate"] == "2026-05-15"


def test_start_point_user_value(client):
    r = client.post(f"/api/v1/prices/{CODE}/start-point",
                    json={"mode": "user_value", "userValue": 205.5, "userNote": "oferta"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["value"] == 205.5
    assert d["mode"] == "user_value"


def test_start_point_index_mode(client):
    r = client.post(f"/api/v1/prices/{CODE}/start-point",
                    json={"mode": "index", "indexCode": "EU_ETS_EUA",
                          "indexFactor": 1.2, "indexOffset": 0})
    assert r.status_code == 200, r.text
    assert "formuła indeksowa" in r.json()["source"]


def test_start_point_empty_window_is_422(client):
    r = client.post(f"/api/v1/prices/{CODE}/start-point",
                    json={"mode": "user_date", "referenceDate": "2000-01-01", "windowDays": 5})
    assert r.status_code == 422


def test_start_point_unknown_mode_is_422(client):
    r = client.post(f"/api/v1/prices/{CODE}/start-point", json={"mode": "wishful"})
    assert r.status_code == 422


def test_forecast_joins_history_and_forecast(client):
    r = client.post(f"/api/v1/prices/{CODE}/forecast",
                    json={"mode": "current", "horizonYears": 5})
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["history"]) > 0
    assert len(d["forecast"]) == 6
    assert d["boundaryDate"] == d["history"][-1]["date"]
    assert d["startPoint"]["observationsUsed"] > 0


def test_forecast_chart_svg(client):
    r = client.get(f"/api/v1/prices/{CODE}/forecast-chart.svg?horizon=5")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/svg+xml"
    assert b"granica historia/prognoza" in r.content
