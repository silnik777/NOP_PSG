"""Price endpoints: current level, ~6-month history, trend, scenarios, and SVG chart."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ...application.price_service import analyze_trend, build_scenario
from ...infrastructure.charts.svg import line_chart
from ...infrastructure.persistence.database import get_session
from ...infrastructure.persistence.price_repository import list_series_codes, load_series
from .schemas import (
    PriceHistoryResponse,
    PricePointDTO,
    PriceSeriesSummary,
    ScenarioBandDTO,
    ScenarioResponse,
    TrendResponse,
)

router = APIRouter(prefix="/api/v1/prices", tags=["prices"])


def _load_or_404(code: str, session: Session):
    series = load_series(session, code)
    if series is None or not series.points:
        raise HTTPException(status_code=404, detail=f"Unknown or empty price series: {code!r}")
    return series


def _point(p) -> PricePointDTO:
    return PricePointDTO(date=p.observed_on, value=p.value)


@router.get("", response_model=list[PriceSeriesSummary])
def list_prices(session: Session = Depends(get_session)) -> list[PriceSeriesSummary]:
    out: list[PriceSeriesSummary] = []
    for code in list_series_codes(session):
        s = load_series(session, code)
        if s and s.points:
            out.append(
                PriceSeriesSummary(
                    code=s.code, name=s.name, unit=s.unit, currency=s.currency,
                    source=s.source, current=_point(s.latest),
                )
            )
    return out


@router.get("/{code}/history", response_model=PriceHistoryResponse)
def history(
    code: str, weeks: int = Query(26, ge=1, le=520), session: Session = Depends(get_session)
) -> PriceHistoryResponse:
    s = _load_or_404(code, session)
    pts = s.points[-weeks:]
    return PriceHistoryResponse(
        code=s.code, name=s.name, unit=s.unit, currency=s.currency, source=s.source,
        current=_point(s.latest), points=[_point(p) for p in pts],
    )


@router.get("/{code}/trend", response_model=TrendResponse)
def trend(code: str, session: Session = Depends(get_session)) -> TrendResponse:
    s = _load_or_404(code, session)
    t = analyze_trend(s)
    return TrendResponse(
        code=s.code, annualizedReturn=t.annualized_return, pctChangeWindow=t.pct_change_window,
        annualizedVolatility=t.annualized_volatility, movingAverageLast=t.moving_average_last,
        movingAverageWindow=t.moving_average_window,
    )


@router.get("/{code}/scenario", response_model=ScenarioResponse)
def scenario(
    code: str,
    startYear: int = Query(2026, ge=2000, le=2100),
    horizon: int = Query(5, ge=1, le=50),
    session: Session = Depends(get_session),
) -> ScenarioResponse:
    s = _load_or_404(code, session)
    sc = build_scenario(s, startYear, horizon)
    return ScenarioResponse(
        seriesCode=sc.series_code, unit=sc.unit, startValue=sc.start_value,
        annualizedReturn=sc.annualized_return,
        bands=[ScenarioBandDTO(year=b.year, low=b.low, base=b.base, high=b.high) for b in sc.bands],
    )


@router.get("/{code}/chart.svg")
def chart(
    code: str, weeks: int = Query(26, ge=2, le=520), session: Session = Depends(get_session)
) -> Response:
    s = _load_or_404(code, session)
    pts = s.points[-weeks:]
    values = [p.value for p in pts]
    labels = [p.observed_on[5:] for p in pts]  # MM-DD
    ma = [sum(values[max(0, i - 3): i + 1]) / len(values[max(0, i - 3): i + 1])
          for i in range(len(values))]
    svg = line_chart(
        s.name, labels,
        [("Cena", values, "#4c9be8"), ("Śr. 4-tyg.", ma, "#f0a35e")],
        unit=s.unit,
    )
    return Response(content=svg, media_type="image/svg+xml")
