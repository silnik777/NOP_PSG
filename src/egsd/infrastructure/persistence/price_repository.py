"""Load price series and points from the store into domain objects."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...domain.prices.models import PricePoint, PriceSeries
from .models import PricePointRow, PriceSeriesRow


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
