"""Seed report-based macro price scenarios (OPZ §8.1 — Scenariusze Makro).

Forward annual paths for gas (TGE), power (TGE) and EU ETS (EUA) for three scenario
families that mirror the institutional reports the OPZ points to:

  * low   — opóźniona transformacja / niskie ceny ETS (EU Reference / IEA WEO STEPS-like)
  * base  — ARE / PEP2040 (KPEiR) ścieżka bazowa
  * high  — wysokie ceny ETS 2026-2040 (Fit-for-55 / IEA WEO APS-like)

Annual values are interpolated from report milestones (2026 / 2035 / 2040 / 2050). They are
illustrative, versioned reference data with source attribution — to be replaced by the actual
report figures kept by the Departament Strategii; the structure and provenance are the point.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import MacroScenarioPointRow, MacroScenarioRow

_BASE_YEAR = 2026
_END_YEAR = 2050

# Scenario metadata.
_SCENARIOS: list[dict] = [
    {
        "code": "MACRO-DELAYED-LOW", "name": "Opóźniona transformacja — niskie ceny ETS",
        "family": "low",
        "source": "EU Reference Scenario 2020 / IEA WEO STEPS (rodzina raportów)",
        "vintage": "2024",
        "notes": "Wolniejsza dekarbonizacja, niższa ścieżka EUA i cen energii.",
    },
    {
        "code": "MACRO-ARE-BASE", "name": "Ścieżka bazowa ARE / PEP2040 (KPEiR)",
        "family": "base",
        "source": "ARE / PEP2040 / KPEiR (Departament Strategii)",
        "vintage": "2025",
        "notes": "Scenariusz odniesienia zgodny z krajową polityką energetyczną.",
    },
    {
        "code": "MACRO-FF55-HIGH", "name": "Wysokie ceny ETS 2026-2040 (Fit-for-55)",
        "family": "high",
        "source": "Fit-for-55 / IEA WEO APS (rodzina raportów)",
        "vintage": "2025",
        "notes": "Przyspieszona dekarbonizacja, wysoka ścieżka EUA, przeniesienie na ceny energii.",
    },
]

# Report milestones per (scenario, commodity): {year: value}. Units match price_series.
# EU ETS in EUR/t; gas & power in PLN/MWh.
_MILESTONES: dict[str, dict[str, dict[int, float]]] = {
    "MACRO-DELAYED-LOW": {
        "EU_ETS_EUA": {2026: 78, 2035: 95, 2040: 105, 2050: 120},
        "PL_GAS_TGE": {2026: 170, 2035: 158, 2040: 150, 2050: 140},
        "PL_POWER_TGE": {2026: 465, 2035: 445, 2040: 430, 2050: 415},
    },
    "MACRO-ARE-BASE": {
        "EU_ETS_EUA": {2026: 82, 2035: 130, 2040: 160, 2050: 205},
        "PL_GAS_TGE": {2026: 172, 2035: 182, 2040: 188, 2050: 195},
        "PL_POWER_TGE": {2026: 470, 2035: 495, 2040: 500, 2050: 485},
    },
    "MACRO-FF55-HIGH": {
        "EU_ETS_EUA": {2026: 88, 2035: 190, 2040: 250, 2050: 300},
        "PL_GAS_TGE": {2026: 176, 2035: 205, 2040: 220, 2050: 235},
        "PL_POWER_TGE": {2026: 480, 2035: 545, 2040: 560, 2050: 520},
    },
}


def _interpolate(milestones: dict[int, float]) -> dict[int, float]:
    """Piecewise-linear annual values across the horizon from sparse milestones."""
    years = sorted(milestones)
    out: dict[int, float] = {}
    for y in range(_BASE_YEAR, _END_YEAR + 1):
        if y in milestones:
            out[y] = float(milestones[y])
            continue
        lo = max((k for k in years if k <= y), default=years[0])
        hi = min((k for k in years if k >= y), default=years[-1])
        if lo == hi:
            out[y] = float(milestones[lo])
        else:
            frac = (y - lo) / (hi - lo)
            out[y] = round(milestones[lo] + (milestones[hi] - milestones[lo]) * frac, 2)
    return out


def seed_macro_scenarios(session: Session) -> None:
    if session.scalar(select(MacroScenarioRow).limit(1)) is not None:
        return
    for meta in _SCENARIOS:
        session.add(MacroScenarioRow(**meta))
        for commodity, milestones in _MILESTONES[meta["code"]].items():
            annual = _interpolate(milestones)
            session.add_all(
                MacroScenarioPointRow(
                    scenario_code=meta["code"], commodity_code=commodity, year=y, value=v
                )
                for y, v in annual.items()
            )
