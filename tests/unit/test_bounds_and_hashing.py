from __future__ import annotations

from egsd.domain.gas.bounds import (
    ABSOLUTE_MAX_PRESSURE_MPA,
    check_point,
    is_hard_out_of_range,
)
from egsd.domain.project.hashing import result_hash


def test_hard_cutoff_rule_w3_4():
    assert is_hard_out_of_range(ABSOLUTE_MAX_PRESSURE_MPA + 0.1)
    assert is_hard_out_of_range(0.0)
    assert not is_hard_out_of_range(5.0)


def test_point_in_range_has_no_violations():
    # Within all envelopes (density up to 30 MPa, JT 250-320 K etc.)
    assert check_point(5.0, 300.0) == []


def test_point_out_of_energy_range_flags_groups():
    violations = check_point(5.0, 400.0)  # above energy/JT/transport upper T
    assert any(v.group.value == "thermodynamic_energy" for v in violations)


def test_result_hash_is_stable_and_order_independent():
    inputs = {"b": 2, "a": 1}
    models = {"GERG-2008": "1.0.0", "ISO-6976": "1.0.0"}
    h1 = result_hash(inputs, models)
    h2 = result_hash({"a": 1, "b": 2}, {"ISO-6976": "1.0.0", "GERG-2008": "1.0.0"})
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_result_hash_changes_with_model_version():
    inputs = {"a": 1}
    assert result_hash(inputs, {"GERG-2008": "1.0.0"}) != result_hash(
        inputs, {"GERG-2008": "1.0.1"}
    )
