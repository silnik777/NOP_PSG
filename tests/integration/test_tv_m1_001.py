"""Acceptance test TV-M1-001 (OPZ §9.2) — compression of an 80/20 CH4/H2 blend.

Document reference: P = 1245.5 kW, T_out = 354.2 K (tolerance +-0.5% / +-0.5 K).

IMPORTANT (verification finding #2): the real-fluid engine (GERG-2008 via CoolProp) does
NOT reproduce the document's reference value — it returns ~2281 kW / ~376 K. An independent
ideal-gas hand-calculation (below) corroborates the engine, not the document. Per the plan,
the reference-comparison test is therefore marked xfail and documents the discrepancy, which
must be reconciled against a REFPROP oracle before formally accepting Module I (decision #3).
"""

from __future__ import annotations

import math

import pytest

from egsd.application.compression_service import CompressionService
from egsd.domain.gas.composition import GasComposition
from egsd.domain.thermo.compression import CompressionInput

# TV-M1-001 inputs.
COMPOSITION = GasComposition.from_mapping({"methane": 0.80, "hydrogen": 0.20})
INPUT = CompressionInput(
    composition=COMPOSITION,
    mass_flow_kg_s=10.0,
    inlet_pressure_mpa=2.0,
    inlet_temperature_k=288.15,
    outlet_pressure_mpa=5.0,
    isentropic_efficiency=0.80,
)
DOC_POWER_KW = 1245.5
DOC_OUTLET_K = 354.2


@pytest.fixture(scope="module")
def result():
    return CompressionService().calculate(INPUT)


def test_engine_self_consistency(result):
    """The engine's internal thermodynamic bookkeeping is self-consistent."""
    # actual head = isentropic head / eta_iz
    assert result.polytropic_head_kj_kg == pytest.approx(
        result.isentropic_head_kj_kg / 0.80, rel=1e-6
    )
    # shaft power = mass flow * actual head
    assert result.required_shaft_power_kw == pytest.approx(
        10.0 * result.polytropic_head_kj_kg, rel=1e-6
    )
    assert result.required_shaft_power_kw > 0
    assert result.outlet_temperature_k > INPUT.inlet_temperature_k


def test_engine_agrees_with_ideal_gas_estimate(result):
    """Independent ideal-gas estimate of isentropic head corroborates the engine.

    Confirms the engine (not the document reference) is the trustworthy side.
    """
    r_universal = 8.314462618
    m_mix = 0.80 * 16.043 + 0.20 * 2.016  # g/mol
    r_specific = r_universal / (m_mix / 1000.0)  # J/(kg*K)
    cp = 2.68e3  # J/(kg*K), representative for the blend near inlet
    k = cp / (cp - r_specific)
    ratio = INPUT.outlet_pressure_mpa / INPUT.inlet_pressure_mpa
    t2s = INPUT.inlet_temperature_k * ratio ** ((k - 1) / k)
    isentropic_head_est = cp / 1000.0 * (t2s - INPUT.inlet_temperature_k)  # kJ/kg
    # Engine isentropic head must be within 10% of the ideal-gas estimate.
    assert result.isentropic_head_kj_kg == pytest.approx(isentropic_head_est, rel=0.10)


def test_engine_is_deterministic():
    """Repeated calculation yields identical results (ADR 0001 determinism)."""
    a = CompressionService().calculate(INPUT)
    b = CompressionService().calculate(INPUT)
    assert a.required_shaft_power_kw == b.required_shaft_power_kw
    assert a.outlet_temperature_k == b.outlet_temperature_k


@pytest.mark.xfail(
    reason="Document reference value (1245.5 kW / 354.2 K) is inconsistent with GERG-2008 "
    "real-fluid thermodynamics; engine returns ~2281 kW / ~376 K. Reconcile with REFPROP "
    "oracle before formal Module I acceptance (verification finding #2).",
    strict=True,
)
def test_matches_document_reference(result):
    assert result.required_shaft_power_kw == pytest.approx(DOC_POWER_KW, rel=0.005)
    assert math.isclose(result.outlet_temperature_k, DOC_OUTLET_K, abs_tol=0.5)
