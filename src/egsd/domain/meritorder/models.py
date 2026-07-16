"""Merit-order domain contracts (OPZ §29 Benchmarking i merit order).

The ranking orders generating technologies by short-run marginal cost of one unit of a
single product (electricity, heat or cooling). Per BEN-MER-003 the marginal cost may include
fuel, auxiliary energy, emission and variable-OPEX components; the *cost boundary* (which of
those are counted) and the *functional unit* are part of the comparability identity — a
ranking that mixes them is blocked (BEN-MER-011). Negative marginal costs are permitted
(BEN-MER-006). This is explicitly NOT a unit-commitment or market model (§29.4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Product(str, Enum):
    ELECTRICITY = "electricity"
    HEAT = "heat"
    COOLING = "cooling"


# Cost components that may enter the marginal cost (the "cost boundary", BEN-MER-011).
COST_COMPONENTS = ("fuel", "aux", "emission", "varopex")


class MeritOrderGatekeeperError(ValueError):
    """BEN-MER-011 — technologies are not comparable; message lists the discrepancies."""


@dataclass(frozen=True)
class MeritOrderTechnology:
    """A MeritOrderTechnology contract (MVP subset of §29.3).

    Prices are per MWh of the relevant energy carrier; efficiency is product energy over
    fuel energy (dimensionless). Emission factor is tonnes CO2 per MWh of fuel *input*.
    """

    tech_id: str
    name: str
    product: Product
    functional_unit: str  # e.g. "MWh_e", "GJ_th" — must match across a ranking
    efficiency: float  # product / fuel energy (0, 1]; use 1.0 for non-fuel carriers
    fuel_price_per_mwh: float = 0.0
    emission_factor_t_per_mwh_fuel: float = 0.0
    co2_price_per_t: float = 0.0
    aux_energy_ratio: float = 0.0  # MWh auxiliary per MWh product
    aux_price_per_mwh: float = 0.0
    variable_opex_per_mwh: float = 0.0  # currency per MWh product
    # Descriptive / provenance (§29.3).
    variant: str = ""
    data_quality: str = "screening"  # device | family | literature | screening
    source: str = ""
    currency: str = "PLN"
    price_year: int | None = None
    geography: str = ""
    data_version: str = ""

    def __post_init__(self) -> None:
        if not 0.0 < self.efficiency <= 1.0:
            raise ValueError(
                f"{self.tech_id}: efficiency must be in (0, 1], got {self.efficiency}."
            )


@dataclass(frozen=True)
class CostDecomposition:
    fuel: float
    aux: float
    emission: float
    varopex: float

    @property
    def total(self) -> float:
        return self.fuel + self.aux + self.emission + self.varopex


@dataclass(frozen=True)
class RankedTechnology:
    tech_id: str
    name: str
    marginal_cost: float  # currency per functional unit
    rank: int
    decomposition: CostDecomposition
    data_quality: str


@dataclass(frozen=True)
class MeritOrderResult:
    product: Product
    functional_unit: str
    cost_boundary: tuple[str, ...]  # subset of COST_COMPONENTS actually counted
    ranking: list[RankedTechnology]
    metadata: dict[str, str] = field(default_factory=dict)
    method: str = "marginal-cost merit order (short-run)"
    notes: list[str] = field(default_factory=list)
