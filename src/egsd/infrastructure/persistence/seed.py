"""Seed the mandatory starter reference data (OPZ §8.1)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ModelVersionRow, ReferenceGasProfileRow

# Mandatory starter gas profiles (OPZ §8.1): high-methane group E, nitrogen-rich Lw,
# and three hydrogen test blends (5%, 10%, 20%).
_STARTER_PROFILES: list[dict] = [
    {
        "code": "REF-GAS-E",
        "name": "Gaz wysokometanowy grupy E",
        "fractions": {"methane": 0.965, "ethane": 0.018, "propane": 0.005,
                      "nitrogen": 0.008, "carbon_dioxide": 0.004},
    },
    {
        "code": "REF-GAS-LW",
        "name": "Gaz zaazotowany Lw",
        "fractions": {"methane": 0.86, "ethane": 0.012, "nitrogen": 0.118,
                      "carbon_dioxide": 0.010},
    },
    {
        "code": "REF-GAS-H2-05",
        "name": "Mieszanka z wodorem 5%",
        "fractions": {"methane": 0.917, "ethane": 0.017, "propane": 0.005,
                      "nitrogen": 0.007, "carbon_dioxide": 0.004, "hydrogen": 0.05},
    },
    {
        "code": "REF-GAS-H2-10",
        "name": "Mieszanka z wodorem 10%",
        "fractions": {"methane": 0.868, "ethane": 0.016, "propane": 0.005,
                      "nitrogen": 0.007, "carbon_dioxide": 0.004, "hydrogen": 0.10},
    },
    {
        "code": "REF-GAS-H2-20",
        "name": "Mieszanka z wodorem 20%",
        "fractions": {"methane": 0.80, "hydrogen": 0.20},
    },
    # Blend feedstock streams (for custom compositions via /api/v1/gas/blend).
    {
        "code": "REF-STREAM-H2-ELX",
        "name": "Wodór z elektrolizy (czysty)",
        "fractions": {"hydrogen": 0.9990, "oxygen": 0.0005, "water": 0.0005},
    },
    {
        "code": "REF-STREAM-SNG",
        "name": "Gaz syntetyczny z metanizacji (SNG)",
        "fractions": {"methane": 0.960, "hydrogen": 0.020, "carbon_dioxide": 0.020},
    },
]

_STARTER_MODELS: list[dict] = [
    {"key": "GERG-2008", "version": "gpe-core-1.0.0-heos",
     "description": "CoolProp HEOS multi-fluid Helmholtz with GERG-2008 binary parameters."},
    {"key": "ISO-6976", "version": "iso6976-1.0.0",
     "description": "Ideal-gas volumetric calorific value and Wobbe index."},
]


def seed_reference_data(session: Session) -> None:
    if session.scalar(select(ReferenceGasProfileRow).limit(1)) is None:
        session.add_all(ReferenceGasProfileRow(**p) for p in _STARTER_PROFILES)
    if session.scalar(select(ModelVersionRow).limit(1)) is None:
        session.add_all(ModelVersionRow(**m) for m in _STARTER_MODELS)
