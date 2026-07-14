"""MCDA service — Gatekeeper check then TOPSIS ranking (OPZ §7.1-7.2, W7.3-W7.4).

TOPSIS: vector-normalize the decision matrix, weight it, find the ideal and anti-ideal
points (respecting stimulant/de-stimulant direction), then rank variants by closeness
to the ideal. Deterministic, no randomness (ADR 0001).
"""

from __future__ import annotations

import math

from ..domain.mcda.models import (
    GatekeeperError,
    RankedVariant,
    RankingResult,
    VariantScore,
    Weights,
)

# Criterion direction: +1 stimulant (more is better), -1 de-stimulant.
_CRITERIA: list[tuple[str, int]] = [
    ("npv", +1),
    ("capex", -1),
    ("co2e_tonnes", -1),
    ("trl", +1),
]


def check_comparability(variants: list[VariantScore]) -> None:
    """W7.1/W7.2 — block ranking when macro assumptions differ; list the exact gaps."""
    stated = [v for v in variants if v.assumptions is not None]
    if len(stated) < 2:
        return
    reference = stated[0]
    problems: list[str] = []
    for other in stated[1:]:
        for gap in reference.assumptions.mismatches(other.assumptions):
            problems.append(
                f"Nie można porównać wariantu '{reference.name}' z '{other.name}': {gap}."
            )
    if problems:
        raise GatekeeperError(
            " ".join(problems)
            + " Zrównaj parametry makroekonomiczne przed uruchomieniem modułu decyzyjnego."
        )


def rank(variants: list[VariantScore], weights: Weights | None = None) -> RankingResult:
    if len(variants) < 2:
        raise ValueError("ranking requires at least two variants.")
    check_comparability(variants)
    w = (weights or Weights()).normalized()
    w_by_key = {"npv": w.npv, "capex": w.capex, "co2e_tonnes": w.co2e, "trl": w.trl}

    # Vector normalization per criterion.
    matrix: dict[str, list[float]] = {
        key: [getattr(v, key) for v in variants] for key, _ in _CRITERIA
    }
    weighted: dict[str, list[float]] = {}
    for key, _ in _CRITERIA:
        norm = math.sqrt(sum(x * x for x in matrix[key]))
        weighted[key] = [
            (x / norm if norm > 0 else 0.0) * w_by_key[key] for x in matrix[key]
        ]

    ideal: dict[str, float] = {}
    anti: dict[str, float] = {}
    for key, direction in _CRITERIA:
        col = weighted[key]
        ideal[key] = max(col) if direction > 0 else min(col)
        anti[key] = min(col) if direction > 0 else max(col)

    closeness: list[float] = []
    for i in range(len(variants)):
        d_plus = math.sqrt(sum((weighted[k][i] - ideal[k]) ** 2 for k, _ in _CRITERIA))
        d_minus = math.sqrt(sum((weighted[k][i] - anti[k]) ** 2 for k, _ in _CRITERIA))
        closeness.append(d_minus / (d_plus + d_minus) if (d_plus + d_minus) > 0 else 0.0)

    order = sorted(range(len(variants)), key=lambda i: closeness[i], reverse=True)
    ranking = [
        RankedVariant(name=variants[i].name, closeness=round(closeness[i], 6), rank=pos + 1)
        for pos, i in enumerate(order)
    ]
    return RankingResult(ranking=ranking, weights=w)
