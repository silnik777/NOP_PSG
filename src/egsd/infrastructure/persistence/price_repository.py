"""Load price series and points from the store into domain objects."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...domain.prices.models import MacroScenario, PricePoint, PriceSeries
from .models import (
    MacroScenarioPointRow,
    MacroScenarioRow,
    PricePointRow,
    PriceSeriesRow,
)


def list_series_codes(session: Session) -> list[str]:
    return list(session.scalars(select(PriceSeriesRow.code)).all())


def load_series(session: Session, code: str) -> PriceSeries | None:
    meta = session.scalar(select(PriceSeriesRow).where(PriceSeriesRow.code == code))
    if meta is None:
        return None
    rows = session.scalars(
        select(PricePointRow)
        .where(PricePointRow.series_code == code)
        .order_by(PricePointRow.observed_on)
    ).all()
    points = [PricePoint(observed_on=r.observed_on, value=r.value) for r in rows]
    return PriceSeries(
        code=meta.code, name=meta.name, unit=meta.unit, currency=meta.currency,
        source=meta.source, points=points,
    )


def list_macro_scenarios(session: Session) -> list[MacroScenario]:
    rows = session.scalars(select(MacroScenarioRow).order_by(MacroScenarioRow.code)).all()
    return [
        MacroScenario(
            code=r.code, name=r.name, family=r.family, source=r.source,
            vintage=r.vintage, notes=r.notes,
        )
        for r in rows
    ]


def load_scenario_path(
    session: Session, scenario_code: str, commodity_code: str
) -> dict[int, float]:
    rows = session.scalars(
        select(MacroScenarioPointRow)
        .where(
            MacroScenarioPointRow.scenario_code == scenario_code,
            MacroScenarioPointRow.commodity_code == commodity_code,
        )
        .order_by(MacroScenarioPointRow.year)
    ).all()
    return {r.year: r.value for r in rows}
