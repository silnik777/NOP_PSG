"""Module II reference case (OPZ Karta Modułu II §4.2): DN500, 50 km, 100 000 Nm3/h.

The OPZ acceptance compares against an industrial simulator (Simone / Pipeline Studio) to
within 1.5%. That tool is not available here, so — as with TV-M1-001 — this suite verifies
internal consistency and cross-checks the Colebrook-White friction factor against the
independent explicit Haaland equation. The industrial-simulator comparison remains a
formal-acceptance step.
"""

from __future__ import annotations

import math

import pytest

from egsd.application.hydraulics_service import HydraulicsService
from egsd.domain.gas.composition import GasComposition
from egsd.domain.hydraulics.models import FlowRegime, HydraulicsInput

COMPOSITION = GasComposition.from_mapping(
    {"methane": 0.965, "ethane": 0.018, "propane": 0.005, "nitrogen": 0.008,
     "carbon_dioxide": 0.004}
)
INPUT = HydraulicsInput(
    composition=COMPOSITION,
    diameter_m=0.5,
    roughness_m=0.012e-3,
    length_m=50_000,
    inlet_pressure_mpa=5.0,
    gas_temperature_k=283.15,
    normal_flow_nm3_h=100_000,
)


@pytest.fixture(scope="module")
def result():
    return HydraulicsService().steady_flow(INPUT)


def test_pressure_drop_is_physical(result):
    assert 0.0 < result.pressure_drop_mpa < INPUT.inlet_pressure_mpa
    assert result.outlet_pressure_mpa == pytest.approx(
        INPUT.inlet_pressure_mpa - result.pressure_drop_mpa, rel=1e-9
    )
    # DN500 / 50 km / 100k Nm3/h is a low-loss case (order 0.1 MPa).
    assert 0.05 < result.pressure_drop_mpa < 0.5


def test_flow_is_turbulent(result):
    assert result.flow_regime is FlowRegime.TURBULENT
    assert result.reynolds_number > 1e6
    assert result.mach_number < 0.3  # incompressible-like, no compressibility warning


def test_friction_factor_matches_haaland(result):
    """Colebrook-White must agree with the explicit Haaland approximation (~1%)."""
    rel_roughness = INPUT.roughness_m / INPUT.diameter_m
    arg = (rel_roughness / 3.7) ** 1.11 + 6.9 / result.reynolds_number
    haaland = (-1.8 * math.log10(arg)) ** -2
    assert result.friction_factor == pytest.approx(haaland, rel=0.02)


def test_deterministic(result):
    again = HydraulicsService().steady_flow(INPUT)
    assert again.outlet_pressure_mpa == result.outlet_pressure_mpa
    assert again.friction_factor == result.friction_factor


def test_linepack_consistent_with_geometry():
    svc = HydraulicsService()
    lp = svc.linepack(INPUT)
    # mass = A * L * rho_avg
    area = math.pi * INPUT.diameter_m**2 / 4.0
    expected_mass_t = area * INPUT.length_m * lp.average_density_kg_m3 / 1000.0
    assert lp.linepack_mass_tonnes == pytest.approx(expected_mass_t, rel=1e-9)
    assert lp.linepack_normal_volume_nm3 > 0
    assert 0 < lp.average_pressure_mpa <= INPUT.inlet_pressure_mpa


def test_capacity_exceeded_raises():
    from egsd.infrastructure.gas_engine.errors import StateSolveError

    # Huge flow through a small pipe at modest inlet pressure -> non-physical outlet.
    over = HydraulicsInput(
        composition=COMPOSITION, diameter_m=0.1, roughness_m=0.012e-3, length_m=50_000,
        inlet_pressure_mpa=2.0, gas_temperature_k=283.15, normal_flow_nm3_h=5_000_000,
    )
    with pytest.raises(StateSolveError):
        HydraulicsService().steady_flow(over)


def test_diameter_out_of_range_rejected():
    with pytest.raises(ValueError):
        HydraulicsInput(
            composition=COMPOSITION, diameter_m=2.0, roughness_m=0.012e-3, length_m=1000,
            inlet_pressure_mpa=5.0, gas_temperature_k=283.15, normal_flow_nm3_h=100_000,
        )
