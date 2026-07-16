"""Price endpoints: current level, ~6-month history, trend, scenarios, and SVG chart."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...application.price_service import (
    analyze_trend,
    build_forecast,
    build_report_scenario,
    build_scenario,
    resolve_start_point,
)
from ...domain.prices.models import AggregationMethod, StartPointMode
from ...infrastructure.charts.svg import history_forecast_chart, line_chart
from ...infrastructure.persistence.database import get_session
from ...infrastructure.persistence.price_repository import (
    list_macro_scenarios,
    list_series_codes,
    load_scenario_path,
    load_series,
)
from .schemas import (
    MacroScenarioDTO,
    PriceHistoryResponse,
    PricePointDTO,
    PriceSeriesSummary,
    ReportScenarioResponse,
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


@router.get("/scenarios/macro", response_model=list[MacroScenarioDTO])
def macro_scenarios(session: Session = Depends(get_session)) -> list[MacroScenarioDTO]:
    return [
        MacroScenarioDTO(
            code=m.code, name=m.name, family=m.family, source=m.source,
            vintage=m.vintage, notes=m.notes,
        )
        for m in list_macro_scenarios(session)
    ]


@router.get("/{code}/report-scenario", response_model=ReportScenarioResponse)
def report_scenario(
    code: str,
    anchor: bool = Query(True, description="Rescale report paths to the current price level"),
    session: Session = Depends(get_session),
) -> ReportScenarioResponse:
    """Report-based low/base/high path anchored on the current observed price level."""
    series = _load_or_404(code, session)
    scenarios = list_macro_scenarios(session)
    family_paths: dict[str, dict[int, float]] = {}
    sources: dict[str, str] = {}
    for macro in scenarios:
        path = load_scenario_path(session, macro.code, code)
        if path:
            family_paths[macro.family] = path
            sources[macro.family] = f"{macro.source} ({macro.vintage})"
    if "base" not in family_paths:
        raise HTTPException(status_code=404, detail=f"No macro scenario covers series {code!r}.")

    rs = build_report_scenario(series, family_paths, sources, anchor=anchor)
    return ReportScenarioResponse(
        seriesCode=rs.series_code, unit=rs.unit, referenceValue=rs.reference_value,
        anchored=rs.anchored, basis=rs.basis, sources=rs.sources,
        bands=[ScenarioBandDTO(year=b.year, low=b.low, base=b.base, high=b.high) for b in rs.bands],
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


# ----- Start point (4 modes, §30.3) + combined history/forecast (PRC) ----------


class StartPointRequest(BaseModel):
    mode: str = Field("current", description="current | user_date | user_value | index")
    windowDays: int = Field(30, ge=1, le=365)
    aggregation: str = Field("mean", description="mean | volume_weighted | median | last")
    referenceDate: str | None = None  # ISO date (mode user_date)
    userValue: float | None = None  # mode user_value
    userNote: str | None = None
    indexCode: str | None = None  # mode index — reference series code
    indexFactor: float = 1.0
    indexOffset: float = 0.0


class StartPointResponse(BaseModel):
    value: float
    unit: str
    mode: str
    method: str
    referenceDate: str
    windowDays: int | None
    observationsUsed: int
    observationDates: list[str]
    source: str
    warnings: list[str]


def _resolve_mode(mode: str) -> StartPointMode:
    try:
        return StartPointMode(mode)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown start-point mode {mode!r}; "
            "choose current | user_date | user_value | index.",
        ) from exc


def _resolve_start_point(code: str, req: StartPointRequest, session: Session):
    s = _load_or_404(code, session)
    mode = _resolve_mode(req.mode)
    try:
        aggregation = AggregationMethod(req.aggregation)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Unknown aggregation {req.aggregation!r}.") \
            from exc
    index_series = None
    if mode is StartPointMode.INDEX:
        if not req.indexCode:
            raise HTTPException(status_code=422, detail="mode 'index' requires indexCode.")
        index_series = _load_or_404(req.indexCode, session)
    try:
        sp = resolve_start_point(
            s, mode, window_days=req.windowDays, aggregation=aggregation,
            reference_date=req.referenceDate, user_value=req.userValue,
            user_note=req.userNote, index_series=index_series,
            index_factor=req.indexFactor, index_offset=req.indexOffset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return s, sp


@router.post("/{code}/start-point", response_model=StartPointResponse)
def start_point(
    code: str, req: StartPointRequest, session: Session = Depends(get_session)
) -> StartPointResponse:
    s, sp = _resolve_start_point(code, req, session)
    return StartPointResponse(
        value=sp.value, unit=s.unit, mode=sp.mode, method=sp.method,
        referenceDate=sp.reference_date, windowDays=sp.window_days,
        observationsUsed=sp.observations_used, observationDates=sp.observation_dates,
        source=sp.source, warnings=list(sp.warnings),
    )


class ForecastRequest(StartPointRequest):
    horizonYears: int = Field(5, ge=1, le=50)
    startYear: int | None = None


class ForecastResponse(BaseModel):
    seriesCode: str
    unit: str
    startPoint: StartPointResponse
    boundaryDate: str
    annualizedReturn: float
    history: list[PricePointDTO]
    forecast: list[ScenarioBandDTO]
    notes: list[str]


@router.post("/{code}/forecast", response_model=ForecastResponse)
def forecast(
    code: str, req: ForecastRequest, session: Session = Depends(get_session)
) -> ForecastResponse:
    """Observed history joined to a forward low/base/high path from the chosen start point,
    with an explicit history→forecast boundary (MVP #16–20, PRC-001/002/003)."""
    s, sp = _resolve_start_point(code, req, session)
    fc = build_forecast(s, sp, req.horizonYears, req.startYear)
    return ForecastResponse(
        seriesCode=fc.series_code, unit=fc.unit,
        startPoint=StartPointResponse(
            value=sp.value, unit=s.unit, mode=sp.mode, method=sp.method,
            referenceDate=sp.reference_date, windowDays=sp.window_days,
            observationsUsed=sp.observations_used, observationDates=sp.observation_dates,
            source=sp.source, warnings=list(sp.warnings),
        ),
        boundaryDate=fc.boundary_date, annualizedReturn=round(fc.annualized_return, 6),
        history=[_point(p) for p in fc.history],
        forecast=[
            ScenarioBandDTO(year=b.year, low=b.low, base=b.base, high=b.high) for b in fc.bands
        ],
        notes=fc.notes,
    )


@router.get("/{code}/forecast-chart.svg")
def forecast_chart(
    code: str,
    mode: str = Query("current"),
    windowDays: int = Query(30, ge=1, le=365),
    aggregation: str = Query("mean"),
    horizon: int = Query(5, ge=1, le=50),
    weeks: int = Query(26, ge=2, le=520),
    session: Session = Depends(get_session),
) -> Response:
    """Chart joining recent history and the forward band, with the transition boundary."""
    req = ForecastRequest(
        mode=mode, windowDays=windowDays, aggregation=aggregation, horizonYears=horizon
    )
    s, sp = _resolve_start_point(code, req, session)
    fc = build_forecast(s, sp, horizon)
    hist = [(p.observed_on[5:], p.value) for p in s.points[-weeks:]]
    forecast_rows = [(str(b.year), b.low, b.base, b.high) for b in fc.bands]
    svg = history_forecast_chart(
        f"{s.name} — historia i prognoza", hist, forecast_rows, unit=s.unit
    )
    return Response(content=svg, media_type="image/svg+xml")
