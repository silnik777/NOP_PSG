"""Device catalog and selection logic."""

from __future__ import annotations

import pytest

from egsd.application.device_selection_service import (
    DutySpec,
    compression_auxiliaries,
    evaluate,
    expansion_auxiliaries,
    select,
)
from egsd.domain.devices.models import DeviceCard, DeviceCategory, MachineRole

RECIP = DeviceCard(
    "CMP-RECIP", "piston", MachineRole.COMPRESSOR, DeviceCategory.RECIPROCATING,
    stage_ratio_min=1.5, stage_ratio_max=4.0, stage_ratio_optimal=3.0,
    isentropic_efficiency_nominal=0.82, ratio_derate=0.15,
    mass_flow_min_kg_s=0.1, mass_flow_max_kg_s=30.0,
)
CENTRIF = DeviceCard(
    "CMP-CENTRIF", "turbo", MachineRole.COMPRESSOR, DeviceCategory.CENTRIFUGAL,
    stage_ratio_min=1.2, stage_ratio_max=2.2, stage_ratio_optimal=1.8,
    isentropic_efficiency_nominal=0.83, ratio_derate=0.20,
    mass_flow_min_kg_s=5.0, mass_flow_max_kg_s=400.0,
)


def test_efficiency_peaks_at_optimal_ratio():
    assert RECIP.efficiency_at(3.0) == pytest.approx(0.82)
    assert RECIP.efficiency_at(1.5) < RECIP.efficiency_at(3.0)
    assert RECIP.efficiency_at(4.0) < RECIP.efficiency_at(3.0)


def test_efficiency_zero_outside_envelope():
    assert RECIP.efficiency_at(5.0) == 0.0
    assert RECIP.efficiency_at(1.0) == 0.0


def test_staging_for_high_ratio():
    # Centrifugal max stage ratio 2.2; overall 12 -> needs multiple stages, each <= 2.2.
    stages = CENTRIF.stages_for(12.0)
    assert stages >= 3
    assert 12.0 ** (1.0 / stages) <= CENTRIF.stage_ratio_max + 1e-9


def test_flow_filters_candidates():
    # Tiny flow: centrifugal (min 5 kg/s) is infeasible; reciprocating feasible.
    duty = DutySpec(overall_ratio=2.5, mass_flow_kg_s=0.5, role=MachineRole.COMPRESSOR)
    assert not evaluate(CENTRIF, duty).feasible
    assert evaluate(RECIP, duty).feasible


def test_select_prefers_higher_effective_efficiency():
    duty = DutySpec(overall_ratio=2.0, mass_flow_kg_s=20.0, role=MachineRole.COMPRESSOR)
    selected, ranked = select([RECIP, CENTRIF], duty)
    assert selected is not None
    assert ranked[0].feasible


def test_compression_auxiliaries_aftercooling_when_hot():
    aux = compression_auxiliaries(stages=2, mass_flow_kg_s=10.0, cp_kj_kgk=2.7,
                                  discharge_temperature_k=360.0)
    kinds = {a.kind for a in aux}
    assert "aftercooling" in kinds  # 360 K > 323.15 K pipe-coating limit
    assert "intercooling" in kinds  # 2 stages
    after = next(a for a in aux if a.kind == "aftercooling")
    assert after.duty_kw > 0


def test_expansion_auxiliaries_preheating_when_cold():
    aux = expansion_auxiliaries(mass_flow_kg_s=10.0, cp_kj_kgk=2.3,
                                outlet_temperature_k=250.0, inlet_temperature_k=288.0)
    assert any(a.kind == "preheating" for a in aux)  # 250 K < 273.15 K hydrate guard
