"""Shared API helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...domain.gas.composition import CompositionError, GasComposition
from ...infrastructure.persistence.models import ReferenceGasProfileRow


def resolve_composition(
    composition_id: str | None, inline: dict[str, float] | None, session: Session
) -> GasComposition:
    """Resolve a composition from an inline mapping or a reference-profile code."""
    if inline:
        return GasComposition.from_mapping(inline)
    if composition_id:
        row = session.scalar(
            select(ReferenceGasProfileRow).where(ReferenceGasProfileRow.code == composition_id)
        )
        if row is None:
            raise CompositionError(f"Unknown reference profile: {composition_id!r}")
        return GasComposition.from_mapping(row.fractions)
    raise CompositionError("Provide either gasComposition or compositionId.")
