"""Shared API helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...domain.gas.composition import CompositionError, GasComposition
from ...infrastructure.persistence.models import ReferenceGasProfileRow
from ...infrastructure.persistence.profile_recipe_repository import latest_profile


def resolve_composition(
    composition_id: str | None, inline: dict[str, float] | None, session: Session
) -> GasComposition:
    """Resolve a composition from an inline mapping, a reference-profile code, or a saved
    user composition-profile code (latest version)."""
    if inline:
        return GasComposition.from_mapping(inline)
    if composition_id:
        row = session.scalar(
            select(ReferenceGasProfileRow).where(ReferenceGasProfileRow.code == composition_id)
        )
        if row is not None:
            return GasComposition.from_mapping(row.fractions)
        own = latest_profile(session, composition_id)
        if own is not None:
            return GasComposition.from_mapping(own.fractions)
        raise CompositionError(f"Unknown profile: {composition_id!r}")
    raise CompositionError("Provide either gasComposition or compositionId.")
