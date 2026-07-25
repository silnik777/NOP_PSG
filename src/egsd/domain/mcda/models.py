"""MCDA (TOPSIS) domain contracts + comparability Gatekeeper (OPZ §7).

Criteria per W7.3: NPV (stimulant), CAPEX (de-stimulant), total CO2e (de-stimulant),
TRL (stimulant). Rankings across variants are blocked unless macro assumptions match
(W7.1/W7.2) — the Gatekeeper reports the exact discrepancies.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class MacroAssumptions:
    """The identity set that must match across compared variants (W7.2)."""

    discount_rate: float
    scenario_code: str  # macro price scenario (e.g. MACRO-ARE-BASE)
    engine_version: str  # GasPropertyEngine version

    def mismatches(self, other: MacroAssumptions) -> list[str]:
        out: list[str] = []
        if abs(self.discount_rate - other.discount_rate) > 1e-9:
            out.append(
                f"stopa dyskontowa {self.discount_rate:.2%} vs {other.discount_rate:.2%}"
            )
        if self.scenario_code != other.scenario_code:
            out.append(f"scenariusz makro {self.scenario_code!r} vs {other.scenario_code!r}")
        if self.engine_version != other.engine_version:
            out.append(f"wersja silnika {self.engine_version!r} vs {other.engine_version!r}")
        return out


@dataclass(frozen=True)
class VariantScore:
    """One variant's criterion values entering the ranking."""

    name: str
    npv: float  # stimulant
    capex: float  # de-stimulant
    co2e_tonnes: float  # de-stimulant
    trl: float  # stimulant (1-9)
    assumptions: MacroAssumptions | None = None


@dataclass(frozen=True)
class Weights:
    """Criterion weights; normalized so they always sum to 1 (UI: 100%)."""

    npv: float = 0.4
    capex: float = 0.2
    co2e: float = 0.25
    trl: float = 0.15

    def normalized(self) -> Weights:
        total = self.npv + self.capex + self.co2e + self.trl
        if total <= 0:
            raise ValueError("weights must sum to a positive value.")
        return Weights(
            npv=self.npv / total, capex=self.capex / total,
            co2e=self.co2e / total, trl=self.trl / total,
        )


class GatekeeperError(ValueError):
    """W7.1 — variants are not comparable; message lists the discrepancies."""


@dataclass(frozen=True)
class RankedVariant:
    name: str
    closeness: float  # TOPSIS closeness coefficient [0, 1]
    rank: int


@dataclass(frozen=True)
class RankingResult:
    ranking: list[RankedVariant]
    weights: Weights
    method: str = "TOPSIS"
    consistency: str = "OK"
    notes: list[str] = field(default_factory=list)
