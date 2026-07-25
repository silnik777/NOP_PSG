"""Finance endpoints: DCF (NPV/IRR/LCO) and one-factor sensitivity (tornado)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...application.finance_service import evaluate, sensitivity
from ...domain.finance.models import DcfInput, LcoKind
from .schemas import (
    DcfRequest,
    DcfResponse,
    SensitivityAxisDTO,
    SensitivityPointDTO,
    TornadoResponse,
)

router = APIRouter(prefix="/api/v1/finance", tags=["finance"])


def _to_input(req: DcfRequest) -> DcfInput:
    return DcfInput(
        capex=req.capex,
        discount_rate=req.discountRate,
        horizon_years=req.horizonYears,
        opex_per_year=req.opexPerYear,
        energy_cost_per_year=req.energyCostPerYear,
        ets_cost_per_year=req.etsCostPerYear,
        revenue_per_year=req.revenuePerYear,
        output_per_year=req.outputPerYear,
    )


@router.post("/dcf", response_model=DcfResponse)
def dcf(req: DcfRequest) -> DcfResponse:
    try:
        kind = LcoKind(req.lcoKind) if req.lcoKind else None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Unknown lcoKind: {req.lcoKind!r}") from exc
    result = evaluate(_to_input(req), kind)
    return DcfResponse(
        npv=result.npv, irr=result.irr, lcoValue=result.lco_value, lcoKind=result.lco_kind,
        netCashFlows=result.net_cash_flows, warnings=list(result.warnings),
    )


@router.post("/sensitivity", response_model=TornadoResponse)
def sensitivity_endpoint(req: DcfRequest) -> TornadoResponse:
    result = sensitivity(_to_input(req))
    return TornadoResponse(
        baseNpv=result.base_npv,
        axes=[
            SensitivityAxisDTO(
                parameter=a.parameter,
                points=[SensitivityPointDTO(deltaPct=p.delta_pct, npv=p.npv) for p in a.points],
            )
            for a in result.axes
        ],
    )
