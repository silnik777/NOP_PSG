from __future__ import annotations

import pytest

from egsd.domain.gas.composition import CompositionError, GasComposition


def test_normalizes_near_unity_input():
    # Small rounding drift (sums to 0.99) is renormalized to exactly 1.0.
    comp = GasComposition.from_mapping({"methane": 0.79, "hydrogen": 0.20})
    assert comp.is_normalized()
    assert comp.fractions["methane"] == pytest.approx(0.79 / 0.99)


def test_rejects_percentage_convention():
    # Percentages summing to 100 are rejected — inputs must be mole fractions (~1.0).
    with pytest.raises(CompositionError):
        GasComposition.from_mapping({"methane": 80, "hydrogen": 20})


def test_accepts_document_camelcase_and_aliases():
    comp = GasComposition.from_mapping(
        {"methane": 0.8, "carbonDioxide": 0.05, "N2": 0.05, "H2": 0.10}
    )
    assert set(comp.fractions) == {"methane", "carbon_dioxide", "nitrogen", "hydrogen"}


def test_rejects_unknown_component():
    with pytest.raises(CompositionError):
        GasComposition.from_mapping({"unobtainium": 1.0})


def test_rejects_far_from_unity():
    with pytest.raises(CompositionError):
        GasComposition.from_mapping({"methane": 0.5})  # sums to 0.5


def test_rejects_negative():
    with pytest.raises(CompositionError):
        GasComposition.from_mapping({"methane": 1.2, "hydrogen": -0.2})


def test_cache_key_is_order_independent():
    a = GasComposition.from_mapping({"methane": 0.8, "hydrogen": 0.2})
    b = GasComposition.from_mapping({"hydrogen": 0.2, "methane": 0.8})
    assert a.cache_key() == b.cache_key()
