"""Unit tests for the price start-point resolution (OPZ §30.3 modes A–D, PRC)."""

from __future__ import annotations

import pytest

from egsd.application.price_service import build_forecast, resolve_start_point
from egsd.domain.prices.models import (
    AggregationMethod,
    PricePoint,
    PriceSeries,
    StartPointMode,
)


def _series(code: str = "TEST") -> PriceSeries:
    # Weekly points across ~10 weeks (mirrors the seeded weekly cadence).
    pts = [
        PricePoint("2026-05-04", 100.0),
        PricePoint("2026-05-11", 110.0),
        PricePoint("2026-05-18", 120.0),
        PricePoint("2026-05-25", 130.0),
        PricePoint("2026-06-01", 140.0),
        PricePoint("2026-06-08", 150.0),
        PricePoint("2026-06-15", 160.0),
        PricePoint("2026-06-22", 170.0),
    ]
    return PriceSeries(code=code, name="Test", unit="PLN/MWh", currency="PLN",
                       source="test", points=pts)


def test_current_window_is_not_observation_count():
    # A 30-day window over weekly data contains ~4-5 observations, not 30 (§30.3).
    sp = resolve_start_point(_series(), StartPointMode.CURRENT, window_days=30)
    assert sp.window_days == 30
    assert sp.observations_used <= 6
    assert sp.observations_used >= 4
    assert any("30 dni" in w for w in sp.warnings)
    assert sp.reference_date == "2026-06-22"


def test_current_mean_vs_last_aggregation():
    mean = resolve_start_point(_series(), StartPointMode.CURRENT, window_days=60,
                               aggregation=AggregationMethod.MEAN)
    last = resolve_start_point(_series(), StartPointMode.CURRENT, window_days=60,
                               aggregation=AggregationMethod.LAST)
    assert last.value == 170.0  # newest in the window
    assert mean.value != last.value


def test_volume_weighted_falls_back_to_mean_with_warning():
    sp = resolve_start_point(_series(), StartPointMode.CURRENT, window_days=60,
                             aggregation=AggregationMethod.VOLUME_WEIGHTED)
    assert sp.method == "mean"
    assert any("wolumen" in w.lower() for w in sp.warnings)


def test_user_date_uses_exact_observation_set():
    sp = resolve_start_point(_series(), StartPointMode.USER_DATE,
                             reference_date="2026-05-25", window_days=30)
    assert sp.reference_date == "2026-05-25"
    # Only observations up to and within 30 days before the chosen date.
    assert all(d <= "2026-05-25" for d in sp.observation_dates)
    assert sp.observations_used >= 1


def test_user_date_missing_data_raises():
    with pytest.raises(ValueError, match="Brak obserwacji"):
        resolve_start_point(_series(), StartPointMode.USER_DATE,
                            reference_date="2000-01-01", window_days=10)


def test_user_value_marks_data_and_warns_without_source():
    sp = resolve_start_point(_series(), StartPointMode.USER_VALUE, user_value=200.0)
    assert sp.value == 200.0
    assert sp.mode == "user_value"
    assert sp.observations_used == 0
    assert any("źródła" in w or "uzasadnienia" in w for w in sp.warnings)


def test_index_mode_is_reproducible_formula():
    idx = _series("IDX")
    sp = resolve_start_point(_series(), StartPointMode.INDEX, index_series=idx,
                             index_factor=2.0, index_offset=5.0)
    assert sp.value == pytest.approx(170.0 * 2.0 + 5.0)
    assert "formuła indeksowa" in sp.source


def test_forecast_joins_history_and_marks_boundary():
    sp = resolve_start_point(_series(), StartPointMode.CURRENT, window_days=30)
    fc = build_forecast(_series(), sp, horizon_years=5)
    assert len(fc.history) == 8
    assert len(fc.bands) == 6  # year 0..5
    assert fc.boundary_date == "2026-06-22"
    # bands widen: high-low spread grows with the horizon.
    first = fc.bands[1].high - fc.bands[1].low
    last = fc.bands[-1].high - fc.bands[-1].low
    assert last >= first
