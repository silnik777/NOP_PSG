"""Device catalog and selection via the API."""

from __future__ import annotations


def test_list_device_catalog(client):
    r = client.get("/api/v1/devices")
    assert r.status_code == 200, r.text
    codes = {d["code"] for d in r.json()}
    assert {"CMP-RECIP", "CMP-CENTRIF", "EXP-TURBO"} <= codes


def test_list_expanders_only(client):
    r = client.get("/api/v1/devices?role=Expander")
    assert r.status_code == 200
    assert all(d["role"] == "Expander" for d in r.json())


def test_select_compressor_picks_and_sizes(client):
    body = {
        "compositionId": "REF-GAS-H2-20",
        "massFlowRate": {"value": 10.0, "unit": "kg/s"},
        "inletPressure": {"value": 2.0, "unit": "MPa"},
        "inletTemperature": {"value": 288.15, "unit": "K"},
        "outletPressureTarget": {"value": 5.0, "unit": "MPa"},
    }
    r = client.post("/api/v1/devices/select-compressor", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["selected"] is not None
    assert data["selected"]["feasible"] is True
    assert 0.5 < data["selected"]["effectiveEfficiency"] <= 0.85
    assert data["requiredShaftPower"]["value"] > 0
    assert data["pressureRatio"] == 2.5
    assert isinstance(data["alternatives"], list)


def test_select_expander_flags_preheating(client):
    # Large pressure drop at a reduction station -> cold outlet -> preheating proposed.
    body = {
        "compositionId": "REF-GAS-E",
        "massFlowRate": {"value": 20.0, "unit": "kg/s"},
        "inletPressure": {"value": 5.0, "unit": "MPa"},
        "inletTemperature": {"value": 288.15, "unit": "K"},
        "outletPressureTarget": {"value": 1.0, "unit": "MPa"},
    }
    r = client.post("/api/v1/devices/select-expander", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["selected"]["category"] in {"TurboExpander", "PistonExpander", "ScrewExpander"}
    assert data["recoveredPower"]["value"] > 0
    kinds = {a["kind"] for a in data["auxiliaries"]}
    assert "preheating" in kinds


def test_select_compressor_rejects_expansion_direction(client):
    body = {
        "compositionId": "REF-GAS-E",
        "massFlowRate": {"value": 10.0, "unit": "kg/s"},
        "inletPressure": {"value": 5.0, "unit": "MPa"},
        "inletTemperature": {"value": 288.15, "unit": "K"},
        "outletPressureTarget": {"value": 2.0, "unit": "MPa"},
    }
    r = client.post("/api/v1/devices/select-compressor", json=body)
    assert r.status_code == 422
