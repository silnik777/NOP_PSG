"""Price analytics: current level, trend, and forward low/base/high scenarios.

Scenarios are anchored on the latest observed price and the trend implied by the history
(linear regression), with bands widening by the historical volatility over the horizon.
This feeds the finance engine's discounted cash-flow inputs.
"""

from __future__ import annotations

import statistics
from datetime import date, timedelta

from ..domain.prices.models import (
    AggregationMethod,
    PriceForecast,
    PriceScenario,
    PriceSeries,
    ReportScenario,
    ScenarioBand,
    StartPoint,
    StartPointMode,
    TrendAnalysis,
)

_WEEKS_PER_YEAR = 52.0
_MAX_BAND = 0.6  # cap the low/high spread at +/-60%
_DEFAULT_WINDOW_DAYS = 30  # §30.3 A default start-point window


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


def _aggregate(values: list[float], dates: list[str], method: AggregationMethod) -> float:
    if method is AggregationMethod.MEAN:
        return sum(values) / len(values)
    if method is AggregationMethod.MEDIAN:
        return statistics.median(values)
    if method in (AggregationMethod.LAST, AggregationMethod.VOLUME_WEIGHTED):
        # LAST: newest observation. VOLUME_WEIGHTED has no volume in bundled data -> handled
        # by the caller (falls back to MEAN with a warning); here treat as LAST if it slips in.
        newest = max(range(len(dates)), key=lambda i: dates[i])
        return values[newest]
    raise ValueError(f"unsupported aggregation method {method!r}")


def resolve_start_point(
    series: PriceSeries,
    mode: StartPointMode,
    *,
    window_days: int = _DEFAULT_WINDOW_DAYS,
    aggregation: AggregationMethod = AggregationMethod.MEAN,
    reference_date: str | None = None,
    user_value: float | None = None,
    user_note: str | None = None,
    index_series: PriceSeries | None = None,
    index_factor: float = 1.0,
    index_offset: float = 0.0,
) -> StartPoint:
    """Resolve a forward-scenario start point in one of the four §30.3 modes.

    Enforces "30 dni ≠ 30 obserwacji": the window is a calendar range, and the number of
    observations actually found inside it is recorded separately.
    """
    warnings: list[str] = []
    if window_days < 1:
        raise ValueError("window_days must be >= 1.")

    if mode is StartPointMode.USER_VALUE:
        if user_value is None:
            raise ValueError("mode 'user_value' requires a start value.")
        if not user_note:
            warnings.append("Wartość użytkownika bez źródła/uzasadnienia (zalecane w §30.3 C).")
        ref = reference_date or series.latest.observed_on
        return StartPoint(
            value=float(user_value), mode=mode.value, method="user_value",
            reference_date=ref, window_days=None, observations_used=0,
            observation_dates=[], source=f"dana użytkownika: {user_note or 'brak komentarza'}",
            warnings=tuple(warnings),
        )

    if mode is StartPointMode.INDEX:
        if index_series is None:
            raise ValueError("mode 'index' requires an index/reference series.")
        base = index_series.latest.value
        value = base * index_factor + index_offset
        return StartPoint(
            value=round(value, 6), mode=mode.value, method="index_formula",
            reference_date=index_series.latest.observed_on, window_days=None,
            observations_used=1, observation_dates=[index_series.latest.observed_on],
            source=(
                f"formuła indeksowa: {index_series.code} × {index_factor} + {index_offset}"
            ),
            warnings=tuple(warnings),
        )

    # Modes A (current) and B (user_date) both aggregate a calendar window of observations.
    if mode is StartPointMode.CURRENT:
        end = _parse_date(series.latest.observed_on)
    elif mode is StartPointMode.USER_DATE:
        if not reference_date:
            raise ValueError("mode 'user_date' requires a reference date.")
        end = _parse_date(reference_date)
    else:  # pragma: no cover - exhaustive
        raise ValueError(f"unsupported mode {mode!r}")

    start = end - timedelta(days=window_days - 1)
    in_window = [
        p for p in series.points if start <= _parse_date(p.observed_on) <= end
    ]
    if not in_window:
        raise ValueError(
            f"Brak obserwacji w oknie {window_days} dni do {end.isoformat()} "
            f"dla serii {series.code!r} (§30.3: zgłoszenie braku danych)."
        )

    method = aggregation
    if aggregation is AggregationMethod.VOLUME_WEIGHTED:
        warnings.append(
            "Brak danych wolumenowych — średnia ważona wolumenem sprowadzona do arytmetycznej."
        )
        method = AggregationMethod.MEAN

    values = [p.value for p in in_window]
    dates = [p.observed_on for p in in_window]
    value = _aggregate(values, dates, method)
    if len(in_window) < window_days:
        warnings.append(
            f"Okno {window_days} dni kalendarzowych zawiera {len(in_window)} obserwacji "
            "(30 dni ≠ 30 obserwacji — uwzględniono częstotliwość szeregu i dni bez notowań)."
        )
    return StartPoint(
        value=round(value, 6), mode=mode.value, method=method.value,
        reference_date=end.isoformat(), window_days=window_days,
        observations_used=len(in_window), observation_dates=sorted(dates),
        source=series.source, warnings=tuple(warnings),
    )


def build_forecast(
    series: PriceSeries,
    start_point: StartPoint,
    horizon_years: int,
    start_year: int | None = None,
) -> PriceForecast:
    """Join observed history to a forward low/base/high path starting at `start_point`,
    with an explicit history→forecast boundary (PRC-002)."""
    trend = analyze_trend(series)
    g = trend.annualized_return
    vol = trend.annualized_volatility
    boundary = series.latest.observed_on
    base_year = start_year if start_year is not None else _parse_date(boundary).year

    bands: list[ScenarioBand] = []
    for t in range(horizon_years + 1):
        base = start_point.value * (1.0 + g) ** t
        spread = min(_MAX_BAND, vol * (t**0.5))
        bands.append(
            ScenarioBand(
                year=base_year + t,
                low=round(base * (1.0 - spread), 4),
                base=round(base, 4),
                high=round(base * (1.0 + spread), 4),
            )
        )
    notes = list(start_point.warnings)
    notes.append(
        f"Historia ({len(series.points)} obserwacji) oddzielona od prognozy; "
        f"granica na {boundary}."
    )
    return PriceForecast(
        series_code=series.code, unit=series.unit, start_point=start_point,
        history=list(series.points), bands=bands, boundary_date=boundary,
        annualized_return=g, notes=notes,
    )


def _parse_date(iso: str) -> date:
    return date.fromisoformat(iso)


def build_report_scenario(
    series: PriceSeries,
    family_paths: dict[str, dict[int, float]],
    sources: dict[str, str],
    anchor: bool = True,
) -> ReportScenario:
    """Report-based low/base/high path.

    History supplies only the reference level: each report family's forward trajectory is
    rescaled so its base year equals the current observed price (when anchor=True). The band
    per year is low=min, base=base-family, high=max across the three anchored families.
    """
    if "base" not in family_paths:
        raise ValueError("a 'base' family path is required.")
    reference = series.latest.value

    def factor(path: dict[int, float]) -> float:
        base_year = min(path)
        base_val = path[base_year]
        return (reference / base_val) if (anchor and base_val) else 1.0

    factors = {fam: factor(path) for fam, path in family_paths.items()}
    years = sorted(set().union(*(set(p) for p in family_paths.values())))

    bands: list[ScenarioBand] = []
    for y in years:
        anchored = {
            fam: round(path[y] * factors[fam], 4)
            for fam, path in family_paths.items()
            if y in path
        }
        base_v = anchored["base"]
        bands.append(
            ScenarioBand(
                year=y,
                low=min(anchored.values()),
                base=base_v,
                high=max(anchored.values()),
            )
        )
    return ReportScenario(
        series_code=series.code, unit=series.unit, reference_value=reference,
        anchored=anchor, basis="; ".join(sorted(set(sources.values()))),
        bands=bands, sources=[f"{fam}: {src}" for fam, src in sorted(sources.items())],
    )
