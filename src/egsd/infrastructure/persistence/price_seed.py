"""Seed market price series with ~6 months of weekly history.

Values are deterministic and illustrative (bundled reference data), sized to realistic
2026 Polish/EU levels. They stand in for a live exchange feed, which is a pluggable
provider activated when a market-data host is allow-listed in the network policy.
Per the OPZ (§8.1, snapshots) analyses must anchor on stored, versioned price data anyway.
"""

from __future__ import annotations

import hashlib
import math
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import PricePointRow, PriceSeriesRow

# Last observation date (kept stable for reproducible charts/tests).
_LAST_DATE = date(2026, 7, 13)
_WEEKS = 26  # ~6 months of weekly points

_SERIES: dict[str, dict] = {
    "PL_GAS_TGE": {
        "name": "Gaz ziemny — TGE (RDNg, Day-Ahead)", "unit": "PLN/MWh", "currency": "PLN",
        "source": "TGE (dane ilustracyjne — do zastąpienia feedem giełdowym)",
        "base": 168.0, "trend": 0.45, "amp": 7.5, "period": 13.0,
    },
    "PL_POWER_TGE": {
        "name": "Energia elektryczna — TGE (RDN, Day-Ahead)", "unit": "PLN/MWh", "currency": "PLN",
        "source": "TGE (dane ilustracyjne)",
        "base": 452.0, "trend": 1.6, "amp": 24.0, "period": 9.0,
    },
    "EU_ETS_EUA": {
        "name": "Uprawnienia do emisji EU ETS (EUA)", "unit": "EUR/t", "currency": "EUR",
        "source": "ICE/EEX (dane ilustracyjne)",
        "base": 76.0, "trend": 0.32, "amp": 3.8, "period": 11.0,
    },
}


def _jitter(code: str, i: int) -> float:
    """Deterministic pseudo-noise in [-0.5, 0.5] (stable across processes — ADR 0001).

    Uses a fixed hash (not Python's per-process-salted hash()) so seeded prices,
    charts and scenarios are byte-for-byte reproducible.
    """
    digest = hashlib.sha256(f"{code}:{i}".encode()).digest()
    return int.from_bytes(digest[:2], "big") / 0xFFFF - 0.5


def _series_points(code: str, cfg: dict) -> list[tuple[str, float]]:
    points: list[tuple[str, float]] = []
    for i in range(_WEEKS):
        d = _LAST_DATE - timedelta(weeks=_WEEKS - 1 - i)
        value = (
            cfg["base"]
            + cfg["trend"] * i
            + cfg["amp"] * math.sin(2 * math.pi * i / cfg["period"])
            + cfg["amp"] * 0.4 * _jitter(code, i)
        )
        points.append((d.isoformat(), round(value, 2)))
    return points


def seed_price_series(session: Session) -> None:
    if session.scalar(select(PriceSeriesRow).limit(1)) is not None:
        return
    for code, cfg in _SERIES.items():
        session.add(
            PriceSeriesRow(
                code=code, name=cfg["name"], unit=cfg["unit"],
                currency=cfg["currency"], source=cfg["source"],
            )
        )
        session.add_all(
            PricePointRow(series_code=code, observed_on=d, value=v)
            for d, v in _series_points(code, cfg)
        )
