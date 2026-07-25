"""Seeded price series must be byte-for-byte reproducible (ADR 0001)."""

from __future__ import annotations

from egsd.infrastructure.persistence.price_seed import _SERIES, _series_points


def test_seed_points_are_deterministic():
    a = _series_points("EU_ETS_EUA", _SERIES["EU_ETS_EUA"])
    b = _series_points("EU_ETS_EUA", _SERIES["EU_ETS_EUA"])
    assert a == b


def test_seed_has_expected_shape():
    pts = _series_points("PL_GAS_TGE", _SERIES["PL_GAS_TGE"])
    assert len(pts) == 26  # ~6 months weekly
    # ISO dates, positive values
    assert all(len(d) == 10 and v > 0 for d, v in pts)
    # last observation is the most recent
    assert pts[-1][0] == "2026-07-13"
