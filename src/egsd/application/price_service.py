"""Price analytics: current level, trend, and forward low/base/high scenarios.

Scenarios are anchored on the latest observed price and the trend implied by the history
(linear regression), with bands widening by the historical volatility over the horizon.
This feeds the finance engine's discounted cash-flow inputs.
"""

from __future__ import annotations

import statistics

from ..domain.prices.models import (
    PriceScenario,
    PriceSeries,
    ScenarioBand,
    TrendAnalysis,
)

_WEEKS_PER_YEAR = 52.0
_MAX_BAND = 0.6  # cap the low/high spread at +/-60%


def _linear_slope(values: list[float]) -> float:
    n = len(values)
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(values) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0:
        return 0.0
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values, strict=True)) / denom


def analyze_trend(series: PriceSeries, moving_average_window: int = 4) -> TrendAnalysis:
    values = [p.value for p in series.points]
    if len(values) < 2:
        raise ValueError("need at least two points for a trend.")
    slope = _linear_slope(values)
    last = values[-1]
    annualized_return = slope * _WEEKS_PER_YEAR / last if last else 0.0
    pct_change = (values[-1] - values[0]) / values[0] if values[0] else 0.0

    returns = [
        (values[i] - values[i - 1]) / values[i - 1]
        for i in range(1, len(values))
        if values[i - 1]
    ]
    weekly_vol = statistics.pstdev(returns) if len(returns) > 1 else 0.0
    annualized_vol = weekly_vol * (_WEEKS_PER_YEAR**0.5)

    w = min(moving_average_window, len(values))
    ma_last = sum(values[-w:]) / w
    return TrendAnalysis(
        slope_per_week=slope,
        annualized_return=annualized_return,
        pct_change_window=pct_change,
        annualized_volatility=annualized_vol,
        moving_average_last=ma_last,
        moving_average_window=w,
    )


def build_scenario(
    series: PriceSeries, start_year: int, horizon_years: int
) -> PriceScenario:
    """Forward low/base/high yearly path from the latest price + trend + volatility."""
    trend = analyze_trend(series)
    start = series.latest.value
    g = trend.annualized_return
    vol = trend.annualized_volatility

    bands: list[ScenarioBand] = []
    for t in range(horizon_years + 1):
        base = start * (1.0 + g) ** t
        spread = min(_MAX_BAND, vol * (t**0.5))
        bands.append(
            ScenarioBand(
                year=start_year + t,
                low=round(base * (1.0 - spread), 4),
                base=round(base, 4),
                high=round(base * (1.0 + spread), 4),
            )
        )
    return PriceScenario(
        series_code=series.code, unit=series.unit, start_value=start,
        annualized_return=g, bands=bands,
    )
