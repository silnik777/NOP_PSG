"""Gas mixture composition — mole-fraction value object.

Component keys use canonical CoolProp fluid names so the composition can be handed
directly to the engine adapter. The document (§2.1) uses English property names
(methane, ethane, ...); those are mapped here to CoolProp names.
"""

from __future__ import annotations

from dataclasses import dataclass

# Canonical component name (document / API)  ->  CoolProp fluid name.
COMPONENT_TO_COOLPROP: dict[str, str] = {
    "methane": "Methane",
    "ethane": "Ethane",
    "propane": "Propane",
    "n_butane": "n-Butane",
    "i_butane": "IsoButane",
    "nitrogen": "Nitrogen",
    "carbon_dioxide": "CarbonDioxide",
    "hydrogen": "Hydrogen",
    "oxygen": "Oxygen",
    "carbon_monoxide": "CarbonMonoxide",
    "water": "Water",
    "helium": "Helium",
}

# Aliases accepted on input (document uses camelCase like carbonDioxide).
_ALIASES: dict[str, str] = {
    "carbondioxide": "carbon_dioxide",
    "co2": "carbon_dioxide",
    "n2": "nitrogen",
    "h2": "hydrogen",
    "ch4": "methane",
    "nbutane": "n_butane",
    "ibutane": "i_butane",
    "isobutane": "i_butane",
    "carbonmonoxide": "carbon_monoxide",
    "co": "carbon_monoxide",
}

_NORMALIZATION_TOLERANCE = 1e-6
_MIN_FRACTION = 1e-12  # CoolProp rejects exact-zero fractions for some binaries.


class CompositionError(ValueError):
    """Raised when a composition is structurally invalid."""


def _canonical_key(raw: str) -> str:
    key = raw.strip().lower().replace(" ", "_").replace("-", "_")
    key = _ALIASES.get(key.replace("_", ""), key)
    if key not in COMPONENT_TO_COOLPROP:
        raise CompositionError(f"Unknown gas component: {raw!r}")
    return key


@dataclass(frozen=True)
class GasComposition:
    """Immutable normalized mole-fraction composition."""

    fractions: dict[str, float]  # canonical key -> mole fraction (sums to 1)

    @classmethod
    def from_mapping(cls, raw: dict[str, float]) -> GasComposition:
        if not raw:
            raise CompositionError("Composition is empty.")
        merged: dict[str, float] = {}
        for name, value in raw.items():
            if value is None:
                continue
            if value < 0:
                raise CompositionError(f"Negative mole fraction for {name!r}: {value}")
            merged[_canonical_key(name)] = merged.get(_canonical_key(name), 0.0) + float(value)

        total = sum(merged.values())
        if total <= 0:
            raise CompositionError("Sum of mole fractions must be positive.")
        if abs(total - 1.0) > 0.05:
            raise CompositionError(
                f"Mole fractions sum to {total:.4f}; expected ~1.0 (max 5% deviation before "
                "normalization)."
            )
        # Normalize so fractions sum to exactly 1 (documented behaviour).
        normalized = {k: v / total for k, v in merged.items()}
        return cls(fractions=normalized)

    def coolprop_names(self) -> list[str]:
        return [COMPONENT_TO_COOLPROP[k] for k in self.fractions]

    def coolprop_fractions(self) -> list[float]:
        # Clamp exact zeros away for CoolProp numerical stability.
        return [max(v, _MIN_FRACTION) for v in self.fractions.values()]

    def cache_key(self) -> tuple[tuple[str, float], ...]:
        return tuple(sorted((k, round(v, 12)) for k, v in self.fractions.items()))

    def is_normalized(self) -> bool:
        return abs(sum(self.fractions.values()) - 1.0) <= _NORMALIZATION_TOLERANCE
