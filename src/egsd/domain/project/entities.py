"""Core business hierarchy (OPZ Część B §1): Project -> Variant -> ResultRecord.

These are plain domain dataclasses independent of persistence. The SION rule
(Strict Inheritance with Override Notification) is captured by VariantStatus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class VariantStatus(str, Enum):
    REFERENCE = "Reference"  # Referencyjny — inherits locked reference data
    SIMULATION = "Simulation"  # Symulacyjny/Roboczy — has overrides (amber alert)


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class ModelVersion:
    """A mathematical model approved in the repository (e.g. GERG-2008 v1.0.x)."""

    key: str  # e.g. "GERG-2008"
    version: str  # e.g. "gpe-core-1.0.0-heos"
    description: str = ""


@dataclass
class ReferenceGasProfile:
    """A versioned reference gas composition (OPZ §8.1)."""

    code: str  # e.g. "REF-GAS-E", "REF-GAS-H2-20"
    name: str
    fractions: dict[str, float]
    version: str = "1.0.0"


@dataclass
class ResultRecord:
    """Immutable, signed calculation output (OPZ Część B §1)."""

    record_hash: str  # sha256:...  (identity)
    module: str  # e.g. "thermo.compression"
    inputs: dict
    outputs: dict
    model_versions: dict[str, str]
    result_class: str = "Engineering"
    created_at: datetime = field(default_factory=_utcnow)


@dataclass
class Variant:
    name: str
    status: VariantStatus = VariantStatus.REFERENCE
    overrides: dict[str, object] = field(default_factory=dict)
    results: list[ResultRecord] = field(default_factory=list)

    def apply_override(self, parameter: str, value: object) -> None:
        """Override a reference parameter -> flips to SIMULATION and records the change (SION)."""
        self.overrides[parameter] = value
        self.status = VariantStatus.SIMULATION

    @property
    def has_overrides(self) -> bool:
        return bool(self.overrides)


@dataclass
class Project:
    name: str
    org_unit: str = ""
    variants: list[Variant] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utcnow)

    def add_variant(self, variant: Variant) -> Variant:
        self.variants.append(variant)
        return variant
