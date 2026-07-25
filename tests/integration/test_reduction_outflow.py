"""Modules III (reduction) and IV (blowdown): physics sanity + API contracts."""

from __future__ import annotations

import pytest

from egsd.application.outflow_service import OutflowService
from egsd.application.reduction_service import ReductionService
from egsd.domain.gas.composition import GasComposition
from egsd.domain.outflow.models import BlowdownInput
from egsd.domain.reduction.models import ReductionInput

E_GAS = GasComposition.from_mapping(
    {"methane": 0.965, "ethane": 0.018, "propane": 0.005, "nitrogen": 0.008,
     "carbon_dioxide": 0.004}
)
H2_BLEND = GasComposition.from_mapping({"methane": 0.80, "hydrogen": 0.20})


@pytest.fixture(scope="module")
def reduction_result():
    return ReductionService().station(
        ReductionInput(
            composition=E_GAS, mass_flow_kg_s=20.0, inlet_pressure_mpa=5.0,
            inlet_temperature_k=288.15, outlet_pressure_mpa=1.0,
        )
    )


# ----- Module III ---------------------------------------------------------------


def test_throttle_cools_by_jt(reduction_result):
    t = reduction_result.throttle
    # 5 -> 1 MPa on lean natural gas: JT drop of order 15-25 K, never warming.
    assert 10.0 < t.temperature_drop_k < 30.0
    assert t.outlet_temperature_k < 288.15


def test_throttle_preheat_sized_to_guard(reduction_result):
    t = reduction_result.throttle
    assert t.preheat_required  # 268 K < 278.15 K guard
    assert t.preheat_inlet_temperature_k > 288.15
    assert t.preheater_duty_kw > 0


def test_expander_recovers_power_but_runs_colder(reduction_result):
    e = reduction_result.expander
    assert e.recovered_power_kw > 1000.0
    # Expansion with work extraction cools far more than isenthalpic throttling.
    assert e.outlet_temperature_k < reduction_result.throttle.outlet_temperature_k
    assert e.preheat_required
    assert e.preheater_duty_kw > reduction_result.throttle.preheater_duty_kw


def test_pt_path_stays_above_dew_line(reduction_result):
    assert reduction_result.phase_envelope_available
    margins = [p.margin_k for p in reduction_result.pt_path if p.margin_k is not None]
    assert margins, "expected dew-line margins along the path"
    assert all(m > 0 for m in margins)  # lean E-gas stays safely in the gas phase


def test_reduction_rejects_wrong_direction():
    with pytest.raises(ValueError):
        ReductionInput(
            composition=E_GAS, mass_flow_kg_s=10.0, inlet_pressure_mpa=1.0,
            inlet_temperature_k=288.15, outlet_pressure_mpa=5.0,
        )


# ----- Module IV ----------------------------------------------------------------


@pytest.fixture(scope="module")
def blowdown_result():
    return OutflowService().blowdown(
        BlowdownInput(
            composition=H2_BLEND, initial_pressure_mpa=5.0, gas_temperature_k=283.15,
            orifice_diameter_m=0.10, pipe_diameter_m=0.5, pipe_length_m=10_000,
        )
    )


def test_blowdown_mass_balance(blowdown_result):
    r = blowdown_result
    assert r.initial_inventory_tonnes - r.residual_inventory_tonnes == pytest.approx(
        r.total_released_tonnes, abs=1e-9
    )
    assert sum(r.released_by_component_tonnes.values()) == pytest.approx(
        r.total_released_tonnes, rel=1e-3
    )


def test_blowdown_reaches_atmospheric_and_transitions(blowdown_result):
    r = blowdown_result
    assert r.time_to_atmospheric_min is not None and r.time_to_atmospheric_min > 0
    assert any(p.choked for p in r.profile)  # starts choked at 5 MPa
    assert any(not p.choked for p in r.profile)  # ends subcritical
    # Pressure profile monotonically decreasing.
    pressures = [p.pressure_mpa for p in r.profile]
    assert pressures == sorted(pressures, reverse=True)


def test_blowdown_feeds_scope1(blowdown_result):
    r = blowdown_result
    expected = r.methane_released_tonnes * 29.8 + r.hydrogen_released_tonnes * 11.0
    assert r.co2e_scope1_tonnes == pytest.approx(expected, rel=1e-9)


def test_blowdown_input_validation():
    with pytest.raises(ValueError):
        BlowdownInput(
            composition=H2_BLEND, initial_pressure_mpa=0.05,  # below ambient
            gas_temperature_k=283.15, orifice_diameter_m=0.1, volume_m3=100.0,
        )
    with pytest.raises(ValueError):
        BlowdownInput(
            composition=H2_BLEND, initial_pressure_mpa=5.0, gas_temperature_k=283.15,
            orifice_diameter_m=0.1,  # no inventory definition
        )


# ----- API ------------------------------------------------------------------------


def test_reduction_station_endpoint(client):
    r = client.post(
        "/api/v1/reduction/station",
        json={
            "compositionId": "REF-GAS-E",
            "massFlowRate": {"value": 20.0, "unit": "kg/s"},
            "inletPressure": {"value": 5.0, "unit": "MPa"},
            "inletTemperature": {"value": 288.15, "unit": "K"},
            "outletPressureTarget": {"value": 1.0, "unit": "MPa"},
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["throttle"]["preheatRequired"] is True
    assert data["expander"]["recoveredPower"]["value"] > 0
    assert data["phaseEnvelopeAvailable"] is True
    assert len(data["ptPath"]) >= 10


def test_blowdown_endpoint(client):
    r = client.post(
        "/api/v1/outflow/blowdown",
        json={
            "compositionId": "REF-GAS-H2-20",
            "initialPressure": {"value": 5.0, "unit": "MPa"},
            "gasTemperature": {"value": 283.15, "unit": "K"},
            "orificeDiameter": {"value": 100, "unit": "mm"},
            "pipeDiameter": {"value": 0.5, "unit": "m"},
            "pipeLength": {"value": 10, "unit": "km"},
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["totalReleased"]["value"] > 0
    assert data["co2eScope1"]["value"] > 0
    assert data["timeToAtmospheric"]["value"] > 0
    assert data["releasedByComponent"]["methane"] > data["releasedByComponent"]["hydrogen"]
