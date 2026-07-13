"""Gas-quality assessment and conditioning proposals (propanization / ballasting).

Checks a composition against the high-methane (group E) specification and, when a blend
falls below spec, proposes a conditioning action:
  - Wobbe / calorific value too LOW  -> propanization (add propane, C3H8).
  - Wobbe too HIGH                   -> ballasting (add nitrogen, N2).

Both actions are solved numerically (Brent) on the ISO 6976 property that is out of spec.
Reference limits default to the Polish group-E grid spec and are overridable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from scipy.optimize import brentq

from ..domain.gas.composition import GasComposition
from ..infrastructure.gas_engine.iso6976 import combustion_properties


@dataclass(frozen=True)
class QualityLimits:
    """Group-E high-methane spec (defaults ~ Polish grid code, 25/0 reference)."""

    wobbe_min_mj_m3: float = 45.0
    wobbe_max_mj_m3: float = 56.9
    gross_cv_min_mj_m3: float = 34.0
    reference_pair: str = "25/0"


@dataclass(frozen=True)
class ConditioningProposal:
    action: str  # "propanization" | "ballasting_n2" | "none"
    additive: str  # "propane" | "nitrogen" | ""
    additive_fraction_mol: float  # mole fraction of additive in the FINAL mixture
    resulting_wobbe_mj_m3: float
    resulting_gross_cv_mj_m3: float
    note: str = ""


@dataclass(frozen=True)
class QualityResult:
    within_spec: bool
    wobbe_mj_m3: float
    gross_cv_mj_m3: float
    relative_density: float
    violations: list[str] = field(default_factory=list)
    proposal: ConditioningProposal | None = None


def _with_additive(comp: GasComposition, additive: str, x_add: float) -> GasComposition:
    """Composition after adding `additive` so it is fraction x_add of the final mixture."""
    scaled = {k: v * (1.0 - x_add) for k, v in comp.fractions.items()}
    scaled[additive] = scaled.get(additive, 0.0) + x_add
    return GasComposition.from_mapping(scaled)


def assess(comp: GasComposition, limits: QualityLimits | None = None) -> QualityResult:
    lim = limits or QualityLimits()
    cb = combustion_properties(comp, lim.reference_pair)
    wobbe, cv = cb.wobbe_index_mj_m3, cb.gross_calorific_value_mj_m3

    violations: list[str] = []
    if wobbe < lim.wobbe_min_mj_m3:
        violations.append(f"Wobbe {wobbe:.2f} < min {lim.wobbe_min_mj_m3} MJ/m3")
    if wobbe > lim.wobbe_max_mj_m3:
        violations.append(f"Wobbe {wobbe:.2f} > max {lim.wobbe_max_mj_m3} MJ/m3")
    if cv < lim.gross_cv_min_mj_m3:
        violations.append(f"gross calorific value {cv:.2f} < min {lim.gross_cv_min_mj_m3} MJ/m3")

    proposal = _propose(comp, lim, wobbe, cv, violations)
    return QualityResult(
        within_spec=not violations,
        wobbe_mj_m3=wobbe,
        gross_cv_mj_m3=cv,
        relative_density=cb.relative_density,
        violations=violations,
        proposal=proposal,
    )


def _propose(
    comp: GasComposition, lim: QualityLimits, wobbe: float, cv: float, violations: list[str]
) -> ConditioningProposal | None:
    if not violations:
        return None

    # Low Wobbe or low calorific value -> propanization (propane raises both, monotonically).
    if wobbe < lim.wobbe_min_mj_m3 or cv < lim.gross_cv_min_mj_m3:
        def deficit(x_add: float) -> float:
            cb = combustion_properties(_with_additive(comp, "propane", x_add), lim.reference_pair)
            # satisfy the binding lower limit(s); positive when still below spec
            return min(
                cb.wobbe_index_mj_m3 - lim.wobbe_min_mj_m3,
                cb.gross_calorific_value_mj_m3 - lim.gross_cv_min_mj_m3,
            )

        x = _solve_addition(deficit)
        if x is None:
            return ConditioningProposal(
                action="propanization", additive="propane", additive_fraction_mol=float("nan"),
                resulting_wobbe_mj_m3=wobbe, resulting_gross_cv_mj_m3=cv,
                note="Propane addition up to 50% mol did not restore spec; review the blend.",
            )
        cb = combustion_properties(_with_additive(comp, "propane", x), lim.reference_pair)
        return ConditioningProposal(
            action="propanization", additive="propane", additive_fraction_mol=x,
            resulting_wobbe_mj_m3=cb.wobbe_index_mj_m3,
            resulting_gross_cv_mj_m3=cb.gross_calorific_value_mj_m3,
            note=f"Add {x * 100:.2f}% mol propane to restore group-E spec.",
        )

    # High Wobbe -> ballasting with nitrogen (lowers Wobbe).
    def excess(x_add: float) -> float:
        cb = combustion_properties(_with_additive(comp, "nitrogen", x_add), lim.reference_pair)
        return lim.wobbe_max_mj_m3 - cb.wobbe_index_mj_m3  # positive once within spec

    x = _solve_addition(excess)
    if x is None:
        return None
    cb = combustion_properties(_with_additive(comp, "nitrogen", x), lim.reference_pair)
    return ConditioningProposal(
        action="ballasting_n2", additive="nitrogen", additive_fraction_mol=x,
        resulting_wobbe_mj_m3=cb.wobbe_index_mj_m3,
        resulting_gross_cv_mj_m3=cb.gross_calorific_value_mj_m3,
        note=f"Add {x * 100:.2f}% mol nitrogen to bring Wobbe within the upper limit.",
    )


def _solve_addition(gap) -> float | None:
    """Smallest additive mole fraction in (0, 0.5] making `gap(x) >= 0`, else None."""
    if gap(0.0) >= 0:
        return 0.0
    if gap(0.5) < 0:
        return None
    return brentq(gap, 0.0, 0.5, xtol=1e-6)
