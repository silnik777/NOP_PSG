"""CoreMeritOrderEngine — short-run marginal-cost ranking of generating technologies.

Implements OPZ §29 (BEN-MER). One ranking covers a single product (electricity, heat or
cooling — BEN-MER-001). The marginal cost of one product unit is decomposed into fuel,
auxiliary-energy, emission and variable-OPEX terms (BEN-MER-009); the caller chooses which
of those enter the ranking via the cost boundary (BEN-MER-003). Technologies with mismatched
functional units cannot be ranked together (BEN-MER-011). Negative marginal costs are kept,
not clamped (BEN-MER-006). Every result carries full provenance (BEN-MER-013).
"""

from __future__ import annotations

from datetime import UTC, datetime

from ..domain.meritorder.models import (
    COST_COMPONENTS,
    CostDecomposition,
    MeritOrderGatekeeperError,
    MeritOrderResult,
    MeritOrderTechnology,
    Product,
    RankedTechnology,
)
from ..domain.project.hashing import result_hash

MERIT_ORDER_VERSION = "1.0.0"


def _decompose(t: MeritOrderTechnology) -> CostDecomposition:
    """Marginal cost of one unit of product, split into its four components."""
    fuel = t.fuel_price_per_mwh / t.efficiency
    emission = t.emission_factor_t_per_mwh_fuel / t.efficiency * t.co2_price_per_t
    aux = t.aux_energy_ratio * t.aux_price_per_mwh
    varopex = t.variable_opex_per_mwh
    return CostDecomposition(fuel=fuel, aux=aux, emission=emission, varopex=varopex)


def _bounded_total(d: CostDecomposition, boundary: tuple[str, ...]) -> float:
    return sum(getattr(d, c) for c in boundary)


def build_merit_order(
    technologies: list[MeritOrderTechnology],
    product: Product,
    cost_boundary: tuple[str, ...] = COST_COMPONENTS,
    metadata: dict[str, str] | None = None,
) -> MeritOrderResult:
    """Rank the technologies of a single product by marginal cost (ascending)."""
    for c in cost_boundary:
        if c not in COST_COMPONENTS:
            raise ValueError(f"Unknown cost component {c!r}; allowed: {COST_COMPONENTS}.")
    boundary = tuple(c for c in COST_COMPONENTS if c in cost_boundary)  # canonical order
    if not boundary:
        raise ValueError("Cost boundary must include at least one cost component.")

    subset = [t for t in technologies if t.product == product]
    if not subset:
        raise ValueError(f"No technologies for product {product.value!r}.")

    # BEN-MER-011 — block a ranking that mixes functional units.
    units = {t.functional_unit for t in subset}
    if len(units) > 1:
        details = ", ".join(
            f"{t.tech_id}={t.functional_unit!r}" for t in subset
        )
        raise MeritOrderGatekeeperError(
            "Nie można utworzyć wspólnego rankingu — niezgodne jednostki funkcjonalne: "
            f"{sorted(units)}. Szczegóły: {details}."
        )
    functional_unit = units.pop()

    scored = [(t, _decompose(t)) for t in subset]
    scored.sort(key=lambda pair: (_bounded_total(pair[1], boundary), pair[0].tech_id))

    ranking: list[RankedTechnology] = []
    notes: list[str] = []
    for i, (t, d) in enumerate(scored, start=1):
        total = _bounded_total(d, boundary)
        ranking.append(
            RankedTechnology(
                tech_id=t.tech_id, name=t.name, marginal_cost=total, rank=i,
                decomposition=d, data_quality=t.data_quality,
            )
        )
        if total < 0:
            notes.append(
                f"{t.tech_id}: ujemny koszt krańcowy ({total:.2f}) — zachowany (BEN-MER-006)."
            )
        if t.data_quality == "screening":
            notes.append(f"{t.tech_id}: dane screeningowe — pozycja orientacyjna.")

    meta = dict(metadata or {})
    meta.setdefault("computedAt", datetime.now(UTC).isoformat())
    meta.setdefault("engineVersion", MERIT_ORDER_VERSION)
    checksum_inputs = {
        "product": product.value,
        "costBoundary": list(boundary),
        "technologies": [
            {
                "id": t.tech_id, "eff": round(t.efficiency, 9),
                "fuel": t.fuel_price_per_mwh, "ef": t.emission_factor_t_per_mwh_fuel,
                "co2": t.co2_price_per_t, "auxR": t.aux_energy_ratio,
                "auxP": t.aux_price_per_mwh, "vopex": t.variable_opex_per_mwh,
                "unit": t.functional_unit, "ver": t.data_version,
            }
            for t in subset
        ],
    }
    meta["configChecksum"] = result_hash(
        checksum_inputs, {"meritOrder": MERIT_ORDER_VERSION}
    )
    return MeritOrderResult(
        product=product, functional_unit=functional_unit, cost_boundary=boundary,
        ranking=ranking, metadata=meta, notes=notes,
    )
