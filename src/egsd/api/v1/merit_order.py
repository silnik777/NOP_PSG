"""Merit-order endpoints (§29 BEN-MER): marginal-cost ranking for electricity/heat/cooling."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...application.merit_order_service import build_merit_order
from ...domain.meritorder.models import (
    COST_COMPONENTS,
    MeritOrderGatekeeperError,
    MeritOrderTechnology,
    Product,
)

router = APIRouter(prefix="/api/v1/merit-order", tags=["merit-order"])


class TechnologyDTO(BaseModel):
    techId: str
    name: str
    functionalUnit: str
    efficiency: float
    fuelPricePerMwh: float = 0.0
    emissionFactorTPerMwhFuel: float = 0.0
    co2PricePerT: float = 0.0
    auxEnergyRatio: float = 0.0
    auxPricePerMwh: float = 0.0
    variableOpexPerMwh: float = 0.0
    variant: str = ""
    dataQuality: str = "screening"
    source: str = ""
    currency: str = "PLN"
    priceYear: int | None = None
    geography: str = ""
    dataVersion: str = ""


class MeritOrderRequest(BaseModel):
    product: str = Field(description="electricity | heat | cooling")
    technologies: list[TechnologyDTO]
    costBoundary: list[str] = Field(default_factory=lambda: list(COST_COMPONENTS))
    metadata: dict[str, str] = Field(default_factory=dict)


class DecompositionDTO(BaseModel):
    fuel: float
    aux: float
    emission: float
    varopex: float
    total: float


class RankedTechnologyDTO(BaseModel):
    techId: str
    name: str
    marginalCost: float
    rank: int
    decomposition: DecompositionDTO
    dataQuality: str


class MeritOrderResponse(BaseModel):
    product: str
    functionalUnit: str
    costBoundary: list[str]
    method: str
    ranking: list[RankedTechnologyDTO]
    metadata: dict[str, str]
    notes: list[str]


@router.post("", response_model=MeritOrderResponse)
def merit_order(req: MeritOrderRequest) -> MeritOrderResponse:
    try:
        product = Product(req.product)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown product {req.product!r}; choose electricity | heat | cooling.",
        ) from exc

    techs = [
        MeritOrderTechnology(
            tech_id=t.techId, name=t.name, product=product,
            functional_unit=t.functionalUnit, efficiency=t.efficiency,
            fuel_price_per_mwh=t.fuelPricePerMwh,
            emission_factor_t_per_mwh_fuel=t.emissionFactorTPerMwhFuel,
            co2_price_per_t=t.co2PricePerT, aux_energy_ratio=t.auxEnergyRatio,
            aux_price_per_mwh=t.auxPricePerMwh, variable_opex_per_mwh=t.variableOpexPerMwh,
            variant=t.variant, data_quality=t.dataQuality, source=t.source,
            currency=t.currency, price_year=t.priceYear, geography=t.geography,
            data_version=t.dataVersion,
        )
        for t in req.technologies
    ]
    try:
        result = build_merit_order(
            techs, product, tuple(req.costBoundary), req.metadata or None
        )
    except MeritOrderGatekeeperError as exc:
        # BEN-MER-011 — explicit blocking with the discrepancy list.
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return MeritOrderResponse(
        product=result.product.value,
        functionalUnit=result.functional_unit,
        costBoundary=list(result.cost_boundary),
        method=result.method,
        ranking=[
            RankedTechnologyDTO(
                techId=r.tech_id, name=r.name, marginalCost=round(r.marginal_cost, 4),
                rank=r.rank, dataQuality=r.data_quality,
                decomposition=DecompositionDTO(
                    fuel=round(r.decomposition.fuel, 4), aux=round(r.decomposition.aux, 4),
                    emission=round(r.decomposition.emission, 4),
                    varopex=round(r.decomposition.varopex, 4),
                    total=round(r.decomposition.total, 4),
                ),
            )
            for r in result.ranking
        ],
        metadata=result.metadata,
        notes=result.notes,
    )
