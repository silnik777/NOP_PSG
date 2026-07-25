"""Price-series domain contracts: history, trend analytics and forward scenarios."""

from __future__ import annotations

from dataclasses import dataclass


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
class ReportScenario:
    series_code: str
    unit: str
    reference_value: float  # current observed level (history anchor)
    anchored: bool
    basis: str  # report attribution summary
    bands: list[ScenarioBand]
    sources: list[str]
