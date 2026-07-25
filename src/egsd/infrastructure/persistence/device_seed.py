"""Seed the compressor/expander technology catalog (device cards)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import DeviceCardRow

# Representative engineering envelopes per technology. Ratios are per-stage.
_DEVICE_CARDS: list[dict] = [
    # --- Compressors ---
    {
        "code": "CMP-RECIP", "name": "Sprężarka tłokowa (reciprocating)",
        "role": "Compressor", "category": "Reciprocating",
        "stage_ratio_min": 1.5, "stage_ratio_max": 4.0, "stage_ratio_optimal": 3.0,
        "isentropic_efficiency_nominal": 0.82, "ratio_derate": 0.15,
        "mass_flow_min_kg_s": 0.1, "mass_flow_max_kg_s": 30.0,
        "max_discharge_temperature_k": 453.15,
        "notes": "Wysokie spręże, niskie/średnie przepływy; dobra dla H2 (niska masa cząst.).",
    },
    {
        "code": "CMP-SCREW", "name": "Sprężarka śrubowa (screw)",
        "role": "Compressor", "category": "Screw",
        "stage_ratio_min": 1.5, "stage_ratio_max": 4.0, "stage_ratio_optimal": 3.0,
        "isentropic_efficiency_nominal": 0.75, "ratio_derate": 0.12,
        "mass_flow_min_kg_s": 0.2, "mass_flow_max_kg_s": 25.0,
        "max_discharge_temperature_k": 423.15,
        "notes": "Średnie przepływy, praca ciągła, toleruje zabrudzenia.",
    },
    {
        "code": "CMP-ROOTS", "name": "Dmuchawa Rootsa (lobe)",
        "role": "Compressor", "category": "Roots",
        "stage_ratio_min": 1.05, "stage_ratio_max": 2.0, "stage_ratio_optimal": 1.5,
        "isentropic_efficiency_nominal": 0.65, "ratio_derate": 0.25,
        "mass_flow_min_kg_s": 0.5, "mass_flow_max_kg_s": 50.0,
        "max_discharge_temperature_k": 393.15,
        "notes": "Duże przepływy, mały spręż (podbicie ciśnienia).",
    },
    {
        "code": "CMP-SCROLL", "name": "Sprężarka spiralna (scroll)",
        "role": "Compressor", "category": "Scroll",
        "stage_ratio_min": 1.5, "stage_ratio_max": 3.5, "stage_ratio_optimal": 2.5,
        "isentropic_efficiency_nominal": 0.70, "ratio_derate": 0.18,
        "mass_flow_min_kg_s": 0.01, "mass_flow_max_kg_s": 2.0,
        "max_discharge_temperature_k": 423.15,
        "notes": "Małe przepływy, cicha, olejowa/bezolejowa.",
    },
    {
        "code": "CMP-CENTRIF", "name": "Sprężarka odśrodkowa (turbo/centrifugal)",
        "role": "Compressor", "category": "Centrifugal",
        "stage_ratio_min": 1.2, "stage_ratio_max": 2.2, "stage_ratio_optimal": 1.8,
        "isentropic_efficiency_nominal": 0.83, "ratio_derate": 0.20,
        "mass_flow_min_kg_s": 5.0, "mass_flow_max_kg_s": 400.0,
        "max_discharge_temperature_k": 473.15,
        "notes": "Bardzo duże przepływy, umiarkowany spręż na stopień; standard tłoczni.",
    },
    # --- Expanders ---
    {
        "code": "EXP-TURBO", "name": "Turboekspander (radialny)",
        "role": "Expander", "category": "TurboExpander",
        "stage_ratio_min": 1.5, "stage_ratio_max": 5.0, "stage_ratio_optimal": 3.5,
        "isentropic_efficiency_nominal": 0.85, "ratio_derate": 0.15,
        "mass_flow_min_kg_s": 1.0, "mass_flow_max_kg_s": 200.0,
        "notes": "Odzysk energii na stacjach redukcyjnych; wysoka sprawność.",
    },
    {
        "code": "EXP-PISTON", "name": "Ekspander tłokowy",
        "role": "Expander", "category": "PistonExpander",
        "stage_ratio_min": 1.5, "stage_ratio_max": 5.0, "stage_ratio_optimal": 3.0,
        "isentropic_efficiency_nominal": 0.75, "ratio_derate": 0.15,
        "mass_flow_min_kg_s": 0.1, "mass_flow_max_kg_s": 15.0,
        "notes": "Mniejsze przepływy, wysokie spręże rozprężania.",
    },
    {
        "code": "EXP-SCREW", "name": "Ekspander śrubowy",
        "role": "Expander", "category": "ScrewExpander",
        "stage_ratio_min": 1.3, "stage_ratio_max": 4.0, "stage_ratio_optimal": 2.5,
        "isentropic_efficiency_nominal": 0.70, "ratio_derate": 0.15,
        "mass_flow_min_kg_s": 0.2, "mass_flow_max_kg_s": 20.0,
        "notes": "Toleruje przepływ dwufazowy/wilgotny.",
    },
    {
        "code": "EXP-SCROLL", "name": "Ekspander spiralny (scroll)",
        "role": "Expander", "category": "ScrollExpander",
        "stage_ratio_min": 1.3, "stage_ratio_max": 3.5, "stage_ratio_optimal": 2.3,
        "isentropic_efficiency_nominal": 0.68, "ratio_derate": 0.18,
        "mass_flow_min_kg_s": 0.01, "mass_flow_max_kg_s": 2.0,
        "notes": "Małe przepływy, mikro-odzysk energii (mikro-ORC / stacje pomiarowe).",
    },
    {
        "code": "EXP-ROOTS", "name": "Ekspander Rootsa (lobe)",
        "role": "Expander", "category": "RootsExpander",
        "stage_ratio_min": 1.05, "stage_ratio_max": 2.0, "stage_ratio_optimal": 1.5,
        "isentropic_efficiency_nominal": 0.60, "ratio_derate": 0.25,
        "mass_flow_min_kg_s": 0.5, "mass_flow_max_kg_s": 50.0,
        "notes": "Duże przepływy, mały spręż rozprężania; prosty, tani, niski odzysk.",
    },
]


def seed_device_cards(session: Session) -> None:
    if session.scalar(select(DeviceCardRow).limit(1)) is None:
        session.add_all(DeviceCardRow(**card) for card in _DEVICE_CARDS)
