"""Gas blending — build a custom composition from named streams by share.

Use case (as requested): blend grid gas + electrolytic hydrogen + methanation SNG by
percentage. Shares are treated as molar (volumetric) fractions and normalized to 1.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.gas.composition import CompositionError, GasComposition


@dataclass(frozen=True)
class BlendComponent:
    composition: GasComposition
    share: float  # relative share (molar/volumetric); normalized across the blend


def blend(components: list[BlendComponent]) -> GasComposition:
    """Molar-weighted blend of several streams into one normalized composition."""
    if not components:
        raise CompositionError("At least one stream is required for blending.")
    total_share = sum(c.share for c in components)
    if total_share <= 0:
        raise CompositionError("Sum of stream shares must be positive.")
    if any(c.share < 0 for c in components):
        raise CompositionError("Stream shares must be non-negative.")

    combined: dict[str, float] = {}
    for comp in components:
        weight = comp.share / total_share
        for key, fraction in comp.composition.fractions.items():
            combined[key] = combined.get(key, 0.0) + fraction * weight
    return GasComposition.from_mapping(combined)
