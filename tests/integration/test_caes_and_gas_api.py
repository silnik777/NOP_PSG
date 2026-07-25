"""CAES storage and gas blending/quality via the domain services and API."""

from __future__ import annotations

import pytest

from egsd.application.storage_service import StorageService
from egsd.domain.storage.models import CaesInput


def test_caes_round_trip_is_physical():
    result = StorageService().caes(
        CaesInput(cavern_volume_m3=310_000, max_pressure_mpa=7.0, min_pressure_mpa=4.3)
    )
    assert result.stored_air_mass_max_tonnes > result.working_air_mass_tonnes > 0
    assert result.charge_energy_mwh > result.discharge_energy_mwh > 0
    # CAES round-trip efficiency is realistically below 1 (irreversibilities).
    assert 0.2 < result.round_trip_efficiency < 1.0
    assert result.result_class.value == "Screening"


def test_caes_rejects_bad_pressure_order():
    with pytest.raises(ValueError):
        CaesInput(cavern_volume_m3=1000, max_pressure_mpa=4.0, min_pressure_mpa=5.0)


# ----- API ---------------------------------------------------------------------


def test_blend_endpoint(client):
    r = client.post(
        "/api/v1/gas/blend",
        json={
            "streams": [
                {"compositionId": "REF-GAS-E", "share": 0.7},
                {"compositionId": "REF-STREAM-H2-ELX", "share": 0.2},
                {"compositionId": "REF-STREAM-SNG", "share": 0.1},
            ]
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["composition"]["hydrogen"] > 0.15
    assert data["wobbeIndex"]["value"] > 0
    assert data["grossCalorificValue"]["unit"] == "MJ/m3"


def test_quality_check_endpoint_proposes_propanization(client):
    body = {
        "gasComposition": {
            "methane": 0.6755, "ethane": 0.0126, "propane": 0.0035, "nitrogen": 0.0056,
            "carbon_dioxide": 0.0028, "hydrogen": 0.30,
        }
    }
    r = client.post("/api/v1/gas/quality-check", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["withinSpec"] is False
    assert data["proposal"]["action"] == "propanization"
    assert data["proposal"]["additiveFractionMol"] > 0


def test_caes_endpoint(client):
    r = client.post(
        "/api/v1/storage/caes",
        json={
            "cavernVolume": {"value": 310000, "unit": "m3"},
            "maxPressure": {"value": 7.0, "unit": "MPa"},
            "minPressure": {"value": 4.3, "unit": "MPa"},
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["dischargeEnergy"]["value"] > 0
    assert 0.2 < data["roundTripEfficiency"] < 1.0
    assert data["resultClass"] == "Screening"


def test_storage_linepack_endpoint(client):
    r = client.post(
        "/api/v1/storage/linepack",
        json={
            "compositionId": "REF-GAS-E",
            "diameter": {"value": 0.5, "unit": "m"},
            "roughness": {"value": 0.012, "unit": "mm"},
            "length": {"value": 50, "unit": "km"},
            "inletPressure": {"value": 5.0, "unit": "MPa"},
            "gasTemperature": {"value": 283.15, "unit": "K"},
            "normalFlow": {"value": 100000, "unit": "Nm3/h"},
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["linepackMass"]["value"] > 0
