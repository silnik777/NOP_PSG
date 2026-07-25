"""Finance (DCF) domain contracts (OPZ §5)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class LcoKind(str, Enum):
    LCOE = "LCOE"  # electricity, MWh_e
    LCOH = "LCOH"  # hydrogen, kg or GJ
    LCOHEAT = "LCOHeat"  # heat, GJ_th
    LCOS = "LCOS"  # storage, MWh


@dataclass(frozen=True)
class DcfInput:
    capex: float  # total up-front, year 0 (currency)
    discount_rate: float  # r (fraction)
    horizon_years: int  # N
    # Per-year (length N) cash-flow drivers; year 1..N.
    opex_per_year: list[float]
    energy_cost_per_year: list[float] = field(default_factory=list)
    ets_cost_per_year: list[float] = field(default_factory=list)
    revenue_per_year: list[float] = field(default_factory=list)
    # For LCO metrics: produced output per year (MWh, kg, GJ...).
    output_per_year: list[float] = field(default_factory=list)


@dataclass(frozen=True)
class DcfResult:
    npv: float
    irr: float | None
    lco_value: float | None
    lco_kind: str | None
    net_cash_flows: list[float]  # year 0..N
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class SensitivityPoint:
    delta_pct: float
    npv: float


@dataclass(frozen=True)
class SensitivityAxis:
    parameter: str
    points: list[SensitivityPoint]


@dataclass(frozen=True)
class TornadoResult:
    base_npv: float
    axes: list[SensitivityAxis]
