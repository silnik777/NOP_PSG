"""Device technology catalog — compressor and expander machine cards.

Each card describes a technology's applicability envelope (per-stage pressure ratio, flow)
and an efficiency characteristic (nominal isentropic efficiency derated away from the
technology's optimal pressure ratio). Selection uses these to pick the best machine and
required stage count, instead of a hard-coded efficiency.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class MachineRole(str, Enum):
    COMPRESSOR = "Compressor"
    EXPANDER = "Expander"


class DeviceCategory(str, Enum):
    RECIPROCATING = "Reciprocating"  # piston compressor
    SCREW = "Screw"
    ROOTS = "Roots"  # lobe blower
    SCROLL = "Scroll"
    CENTRIFUGAL = "Centrifugal"  # turbo compressor
    TURBO_EXPANDER = "TurboExpander"
    PISTON_EXPANDER = "PistonExpander"
    SCREW_EXPANDER = "ScrewExpander"
    SCROLL_EXPANDER = "ScrollExpander"
    ROOTS_EXPANDER = "RootsExpander"


@dataclass(frozen=True)
class DeviceCard:
    code: str
    name: str
    role: MachineRole
    category: DeviceCategory
    # Per-stage pressure ratio applicability (p_out/p_in for a compressor;
    # p_in/p_out for an expander).
    stage_ratio_min: float
    stage_ratio_max: float
    stage_ratio_optimal: float
    isentropic_efficiency_nominal: float
    # Derating: fractional efficiency loss at the far edges of the ratio envelope.
    ratio_derate: float
    # Applicability by mass flow (kg/s).
    mass_flow_min_kg_s: float
    mass_flow_max_kg_s: float
    max_discharge_temperature_k: float = 473.15  # compressors; ignored for expanders
    notes: str = ""

    def efficiency_at(self, stage_ratio: float) -> float:
        """Effective isentropic efficiency for a given per-stage ratio (0 outside envelope)."""
        if not self.stage_ratio_min <= stage_ratio <= self.stage_ratio_max:
            return 0.0
        span = max(
            self.stage_ratio_optimal - self.stage_ratio_min,
            self.stage_ratio_max - self.stage_ratio_optimal,
        )
        if span <= 0:
            return self.isentropic_efficiency_nominal
        offset = abs(stage_ratio - self.stage_ratio_optimal) / span
        return self.isentropic_efficiency_nominal * (1.0 - self.ratio_derate * offset**2)

    def stages_for(self, overall_ratio: float) -> int:
        """Number of equal-ratio stages so each stage ratio stays within the envelope."""
        if overall_ratio <= self.stage_ratio_max:
            return 1
        return math.ceil(math.log(overall_ratio) / math.log(self.stage_ratio_max))

    def accepts_flow(self, mass_flow_kg_s: float) -> bool:
        return self.mass_flow_min_kg_s <= mass_flow_kg_s <= self.mass_flow_max_kg_s
