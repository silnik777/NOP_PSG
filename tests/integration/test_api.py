"""API-level integration tests against the document contracts."""

from __future__ import annotations


def test_point_properties_contract(client):
    # Composition and shape from OPZ §2.1.
    body = {
        "meta": {"requestId": "req-test-1", "callerModule": "test"},
        "gasComposition": {
            "methane": 0.8250, "ethane": 0.0210, "propane": 0.0040,
            "nitrogen": 0.0100, "carbonDioxide": 0.0150, "hydrogen": 0.1250,
        },
        "stateVariables": {
            "pressure": {"value": 5.50, "unit": "MPa"},
            "temperature": {"value": 285.15, "unit": "K"},
        },
        "config": {"preferredModel": "GERG-2008", "allowScreeningFallback": False},
    }
    r = client.post("/api/v1/gas-engine/point-properties", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    cv = data["calculatedValues"]
    assert 0.7 < cv["compressibilityFactor"]["value"] < 1.05
    assert cv["density"]["value"] > 0
    assert cv["molarMass"]["unit"] == "kg/kmol"
    assert data["validation"]["isWithinModelRange"] is True
    assert data["meta"]["engineVersion"].startswith("gpe-core")


def test_point_properties_hard_out_of_range_rejected(client):
    body = {
        "gasComposition": {"methane": 0.8, "hydrogen": 0.2},
        "stateVariables": {
            "pressure": {"value": 40.0, "unit": "MPa"},  # > 35 MPa cutoff (W3.4)
            "temperature": {"value": 300.0, "unit": "K"},
        },
    }
    r = client.post("/api/v1/gas-engine/point-properties", json=body)
    assert r.status_code == 422
    assert "W3.4" in r.text or "cutoff" in r.text


def test_combustion_pure_methane(client):
    r = client.post(
        "/api/v1/gas-engine/combustion",
        json={"gasComposition": {"methane": 1.0}, "referencePair": "25/0"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    # Methane HHV ~39.8 MJ/m3, Wobbe ~53.4 MJ/m3 at 0 degC metering.
    assert 39.0 < data["grossCalorificValue"]["value"] < 40.5
    assert 52.5 < data["wobbeIndex"]["value"] < 54.0


def test_compression_via_reference_profile(client):
    r = client.post(
        "/api/v1/thermo/compression",
        json={
            "compositionId": "REF-GAS-H2-20",
            "massFlowRate": {"value": 10.0, "unit": "kg/s"},
            "inletPressure": {"value": 2.0, "unit": "MPa"},
            "inletTemperature": {"value": 288.15, "unit": "K"},
            "outletPressureTarget": {"value": 5.0, "unit": "MPa"},
            "isentropicEfficiency": 0.80,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["requiredShaftPower"]["value"] > 0
    assert data["resultClass"] == "Engineering"


def test_project_variant_result_lifecycle(client):
    # Create project with a variant.
    r = client.post(
        "/api/v1/projects",
        json={"name": "Gazyfikacja rejonu X", "orgUnit": "OSD/Strategia",
              "variants": [{"name": "Wariant 1 — sprężarka tłokowa"}]},
    )
    assert r.status_code == 201, r.text
    project = r.json()
    variant_id = project["variants"][0]["id"]
    assert project["variants"][0]["status"] == "Reference"

    # Attach an immutable, hashed result record.
    payload = {
        "module": "thermo.compression",
        "inputs": {"p_in": 2.0, "p_out": 5.0},
        "outputs": {"power_kw": 2281.1},
        "modelVersions": {"GERG-2008": "gpe-core-1.0.0-heos"},
    }
    r1 = client.post(f"/api/v1/variants/{variant_id}/results", json=payload)
    assert r1.status_code == 201, r1.text
    hash1 = r1.json()["recordHash"]
    assert hash1.startswith("sha256:")

    # Same inputs+models -> same immutable record (idempotent, 200 not 201).
    r2 = client.post(f"/api/v1/variants/{variant_id}/results", json=payload)
    assert r2.status_code == 200
    assert r2.json()["recordHash"] == hash1


def test_reference_profiles_seeded(client):
    r = client.get("/api/v1/reference-profiles")
    assert r.status_code == 200
    codes = {p["code"] for p in r.json()}
    assert {"REF-GAS-E", "REF-GAS-LW", "REF-GAS-H2-20"} <= codes
