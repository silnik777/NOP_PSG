"""CoreFinanceEngine — DCF: NPV, IRR (Brent), unified LCO, one-factor sensitivity.

Single analytical standard for the whole platform (OPZ §5); process modules must not
implement local financial maths.
"""

from __future__ import annotations

from scipy.optimize import brentq

from ..domain.finance.models import (
    DcfInput,
    DcfResult,
    LcoKind,
    SensitivityAxis,
    SensitivityPoint,
    TornadoResult,
)

_SENSITIVITY_STEPS = [-30, -25, -20, -15, -10, -5, 0, 5, 10, 15, 20, 25, 30]  # W5.1


def _pad(values: list[float], n: int) -> list[float]:
    return [values[i] if i < len(values) else 0.0 for i in range(n)]


def net_cash_flows(data: DcfInput) -> list[float]:
    """Year 0..N net cash flows (year 0 = -CAPEX)."""
    n = data.horizon_years
    opex = _pad(data.opex_per_year, n)
    energy = _pad(data.energy_cost_per_year, n)
    ets = _pad(data.ets_cost_per_year, n)
    revenue = _pad(data.revenue_per_year, n)
    flows = [-data.capex]
    for t in range(n):
        flows.append(revenue[t] - opex[t] - energy[t] - ets[t])
    return flows


def npv(rate: float, flows: list[float]) -> float:
    return sum(cf / (1.0 + rate) ** t for t, cf in enumerate(flows))


def irr(flows: list[float]) -> tuple[float | None, str | None]:
    """IRR via Brent; guards non-conventional flows (multiple sign changes)."""
    sign_changes = sum(
        1 for i in range(1, len(flows)) if flows[i] * flows[i - 1] < 0
    )
    if sign_changes == 0:
        return None, "No sign change in cash flows — IRR undefined."
    if sign_changes > 1:
        return None, "Non-conventional cash flows (multiple IRR roots possible)."
    try:
        return brentq(lambda r: npv(r, flows), -0.9499, 10.0, xtol=1e-8), None
    except ValueError:
        return None, "IRR not bracketed in [-95%, 1000%]."


def levelized_cost(data: DcfInput, kind: LcoKind) -> float | None:
    """Unified LCO: discounted costs / discounted output (OPZ §5.1)."""
    n = data.horizon_years
    r = data.discount_rate
    opex = _pad(data.opex_per_year, n)
    energy = _pad(data.energy_cost_per_year, n)
    ets = _pad(data.ets_cost_per_year, n)
    output = _pad(data.output_per_year, n)

    disc_cost = data.capex
    disc_output = 0.0
    for t in range(1, n + 1):
        disc_cost += (opex[t - 1] + energy[t - 1] + ets[t - 1]) / (1.0 + r) ** t
        disc_output += output[t - 1] / (1.0 + r) ** t
    if disc_output <= 0:
        return None
    return disc_cost / disc_output


def evaluate(data: DcfInput, lco_kind: LcoKind | None = None) -> DcfResult:
    flows = net_cash_flows(data)
    value = npv(data.discount_rate, flows)
    rate, irr_warn = irr(flows)
    lco = levelized_cost(data, lco_kind) if lco_kind else None
    warnings = (irr_warn,) if irr_warn else ()
    return DcfResult(
        npv=value, irr=rate, lco_value=lco,
        lco_kind=lco_kind.value if lco_kind else None,
        net_cash_flows=flows, warnings=warnings,
    )


def _scaled(values: list[float], factor: float) -> list[float]:
    return [v * factor for v in values]


def sensitivity(data: DcfInput) -> TornadoResult:
    """One-factor NPV sensitivity (+/-30%, 5% steps) for a tornado chart (W5.1)."""
    base = npv(data.discount_rate, net_cash_flows(data))
    axes: list[SensitivityAxis] = []

    def axis_for(param: str, mutate) -> SensitivityAxis:
        pts: list[SensitivityPoint] = []
        for step in _SENSITIVITY_STEPS:
            factor = 1.0 + step / 100.0
            mutated = mutate(factor)
            pts.append(SensitivityPoint(float(step), npv(mutated.discount_rate,
                                                          net_cash_flows(mutated))))
        return SensitivityAxis(param, pts)

    axes.append(axis_for("capex", lambda f: _replace(data, capex=data.capex * f)))
    axes.append(
        axis_for("energy_cost", lambda f: _replace(
            data, energy_cost_per_year=_scaled(data.energy_cost_per_year, f)))
    )
    axes.append(
        axis_for("revenue", lambda f: _replace(
            data, revenue_per_year=_scaled(data.revenue_per_year, f)))
    )
    axes.append(
        axis_for("discount_rate", lambda f: _replace(data, discount_rate=data.discount_rate * f))
    )
    return TornadoResult(base_npv=base, axes=axes)


def _replace(data: DcfInput, **changes) -> DcfInput:
    from dataclasses import replace

    return replace(data, **changes)
