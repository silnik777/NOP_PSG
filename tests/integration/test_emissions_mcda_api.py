"""Emissions and MCDA API."""

from __future__ import annotations

import pytest


def test_footprint_endpoint(client):
    r = client.post(
        "/api/v1/emissions/footprint",
        json={
            "methaneLeakTonnes": 10.0,
            "gridElectricityMwh": 500.0,
            "hydrogenSuppliedTonnes": 50.0,
            "hydrogenOrigin": "green",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["scope1TCo2e"] == pytest.approx(298.0)
    assert data["scope2TCo2e"] == pytest.approx(298.5)
    assert data["scope3TCo2e"] == pytest.approx(25.0)
    assert data["totalTCo2e"] == pytest.approx(621.5)
    assert "AR6" in data["gwpSource"]


def _variant(name, npv, r=0.06, scen="MACRO-ARE-BASE"):
    return {
        "name": name, "npv": npv, "capex": 6e6, "co2eTonnes": 2000, "trl": 8,
        "assumptions": {
            "discountRate": r, "scenarioCode": scen,
            "engineVersion": "gpe-core-1.0.0-heos",
        },
    }


def test_rank_endpoint(client):
    r = client.post(
        "/api/v1/mcda/rank",
        json={"variants": [_variant("W1", 12e6), _variant("W2", 6e6)]},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["method"] == "TOPSIS"
    assert data["ranking"][0]["name"] == "W1"
    weights = data["weightsApplied"]
    assert sum(weights.values()) == pytest.approx(1.0)


def test_rank_gatekeeper_conflict_returns_409(client):
    r = client.post(
        "/api/v1/mcda/rank",
        json={"variants": [_variant("W1", 12e6, r=0.08), _variant("W2", 6e6, r=0.065)]},
    )
    assert r.status_code == 409
    assert "stopa dyskontowa" in r.json()["detail"]
