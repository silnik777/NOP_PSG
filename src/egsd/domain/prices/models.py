"""Price-series domain contracts: history, trend analytics and forward scenarios."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class StartPointMode(str, Enum):
    """The four forward-scenario start-point modes (OPZ §30.3 A–D)."""

    CURRENT = "current"  # A — from data preceding the scenario date (default 30-day window)
    USER_DATE = "user_date"  # B — reference date chosen by the user
    USER_VALUE = "user_value"  # C — start value supplied by the user
    INDEX = "index"  # D — derived from an index/quotation/formula


class AggregationMethod(str, Enum):
    """How observations inside the start-point window are aggregated (§30.3 A)."""

    MEAN = "mean"
    VOLUME_WEIGHTED = "volume_weighted"
    MEDIAN = "median"
    LAST = "last"


@dataclass(frozen=True)
class StartPoint:
    """A resolved forward-scenario start point with full, reproducible provenance.

    Crucially records `observations_used` separately from `window_days` — a 30-day window is
    NOT 30 observations (§30.3 "30 dni ≠ 30 obserwacji").
    """

    value: float
    mode: str
    method: str  # aggregation method applied, or "n/a"
    reference_date: str  # ISO date the point is anchored to
    window_days: int | None
    observations_used: int
    observation_dates: list[str]
    source: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class PricePoint:
    observed_on: str  # ISO date
    value: float


@dataclass(frozen=True)
class PriceSeries:
    code: str
    name: str
    unit: str
    currency: str
    source: str
    points: list[PricePoint]

    @property
    def latest(self) -> PricePoint:
        return self.points[-1]


@dataclass(frozen=True)
class TrendAnalysis:
    slope_per_week: float
    annualized_return: float  # fraction/year implied by the trend
    pct_change_window: float  # (last - first) / first over the window
    annualized_volatility: float
    moving_average_last: float
    moving_average_window: int


@dataclass(frozen=True)
class ScenarioBand:
    year: int
    low: float
    base: float
    high: float


@dataclass(frozen=True)
class PriceScenario:
    series_code: str
    unit: str
    start_value: float
    annualized_return: float
    bands: list[ScenarioBand]


@dataclass(frozen=True)
class MacroScenario:
    code: str
    name: str
    family: str  # low | base | high
    source: str
    vintage: str
    notes: str


@dataclass(frozen=True)
class PriceForecast:
    """History joined to a forward scenario with an explicit transition boundary (PRC-002)."""

    series_code: str
    unit: str
    start_point: StartPoint
    history: list[PricePoint]  # observed
    bands: list[ScenarioBand]  # forecast (year granularity)
    boundary_date: str  # last observed date = history/forecast transition
    annualized_return: float
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReportScenario:
    series_code: str
    unit: str
    reference_value: float  # current observed level (history anchor)
    anchored: bool
    basis: str  # report attribution summary
    bands: list[ScenarioBand]
    sources: list[str]
