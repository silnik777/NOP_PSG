"""Seed versioned gas-quality requirement sets (OPZ §21, MVP #7).

Values are illustrative reference data (grupa E / high-methane), sized to typical Polish grid
levels. Per OPZ ZP-001 the authoritative document, edition and thresholds are to be confirmed
by the Zamawiający — hence each set carries an explicit source and version, and nothing is
hard-coded in engine logic.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import QualityRequirementSetRow

_SETS: list[dict] = [
    {
        "code": "PL-E-2026", "name": "Gaz wysokometanowy grupy E — sieć dystrybucyjna PL",
        "version": "2026.1", "application": "gaz wysokometanowy E", "geography": "PL",
        "reference_document": "Rozporządzenie systemowe / PN-C-04753 (do potwierdzenia, ZP-001)",
        "reference_pair": "25/0",
        "wobbe_min_mj_m3": 45.0, "wobbe_max_mj_m3": 56.9, "gross_cv_min_mj_m3": 34.0,
        "status": "approved",
        "source": "dane ilustracyjne — do potwierdzenia przez Zamawiającego (ZP-001)",
    },
    {
        "code": "PL-Lw-2026", "name": "Gaz zaazotowany grupy Lw — sieć dystrybucyjna PL",
        "version": "2026.1", "application": "gaz zaazotowany Lw", "geography": "PL",
        "reference_document": "Rozporządzenie systemowe (do potwierdzenia, ZP-001)",
        "reference_pair": "25/0",
        "wobbe_min_mj_m3": 37.8, "wobbe_max_mj_m3": 45.0, "gross_cv_min_mj_m3": 27.0,
        "status": "approved",
        "source": "dane ilustracyjne — do potwierdzenia przez Zamawiającego (ZP-001)",
    },
]


def seed_quality_sets(session: Session) -> None:
    if session.scalar(select(QualityRequirementSetRow).limit(1)) is not None:
        return
    session.add_all(QualityRequirementSetRow(**s) for s in _SETS)
