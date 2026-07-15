"""Compare all five expansion technology classes at one operating point (OPZ §25, EXP-CMP).

The five cards (turboexpander, pneumatic piston, pneumatic screw, Roots, scroll) are evaluated
at the *same* inlet/outlet conditions and mass flow (EXP-CMP-001), each with its own catalog
envelope and characteristic. A class outside its feasibility envelope is reported infeasible
rather than extrapolated (EXP-CMP-003). When an optional cost model is supplied, per-class
CAPEX/OPEX/NPV/LCOE and preheat CO2 are added via the shared finance and combustion engines
(EXP-CMP-005) — never a local re-implementation.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.combustion.models import CombustionInput
from ..domain.devices.models import DeviceCard, MachineRole
from ..domain.finance.models import DcfInput, LcoKind
from ..domain.gas.composition import GasComposition
from ..infrastructure.gas_engine.coolprop_engine import CoolPropGasEngine
from . import combustion_service, finance_service
from .device_selection_service import (
    DutySpec,
    expansion_auxiliaries,
)
from .device_selection_service import (
    evaluate as evaluate_candidate,
)
from .thermo_ops import expand, expand_multistage


@dataclass(frozen=True)
class ExpanderCostModel:
    """Optional simple economics for the point comparison (EXP-CMP-005)."""

    specific_capex_pln_per_kw: float
    fixed_opex_pct_per_year: float  # of CAPEX, per year
    electricity_price_pln_per_mwh: float
    discount_rate: float
    horizon_years: int
    operating_hours_per_year: float
    heater_efficiency: float = 0.9  # preheat gas boiler efficiency


@dataclass(frozen=True)
class ExpanderComparisonRow:
    tech_id: str
    name: str
    category: str
    feasible: bool
    reason: str
    data_quality: str  # device | family | literature | screening (EXP-CMP-002)
    effective_efficiency: float | None = None
    recovered_power_kw: float | None = None
    outlet_temperature_k: float | None = None
    preheat_duty_kw: float | None = None
    cooling_potential_kw: float | None = None
    # Economics / emissions (only when a cost model is supplied).
    capex_pln: float | None = None
    annual_opex_pln: float | None = None
    annual_energy_mwh: float | None = None
    npv_pln: float | None = None
    lcoe_pln_per_mwh: float | None = None
    annual_preheat_co2_t: float | None = None


def compare(
    engine: CoolPropGasEngine,
    cards: list[DeviceCard],
    comp: GasComposition,
    p_in_mpa: float,
    t_in_k: float,
    p_out_mpa: float,
    mass_flow_kg_s: float,
    cost: ExpanderCostModel | None = None,
) -> list[ExpanderComparisonRow]:
    if p_out_mpa >= p_in_mpa:
        raise ValueError("outlet pressure must be below inlet pressure for an expander.")
    expanders = [c for c in cards if c.role == MachineRole.EXPANDER]
    if not expanders:
        raise ValueError("No expander cards in the catalog.")

    duty = DutySpec(
        overall_ratio=p_in_mpa / p_out_mpa, mass_flow_kg_s=mass_flow_kg_s,
        role=MachineRole.EXPANDER,
    )
    cp = engine.point_properties(comp, p_in_mpa, t_in_k).state.specific_heat_cp_kj_kgk

    # Preheat CO2 uses the same fuel's stoichiometric combustion intensity.
    co2_kg_per_gj = combustion_service.evaluate(comp, CombustionInput()).co2_kg_per_gj_input

    rows: list[ExpanderComparisonRow] = []
    for card in sorted(expanders, key=lambda c: c.code):
        cand = evaluate_candidate(card, duty)
        quality = _data_quality(card)
        if not cand.feasible:
            rows.append(
                ExpanderComparisonRow(
                    tech_id=card.code, name=card.name, category=card.category.value,
                    feasible=False, reason=cand.reason, data_quality=quality,
                )
            )
            continue

        # Recoverable power from a reheated multi-stage train (matches select-expander);
        # single-stage outlet reveals the condensation/freeze risk driving preheat & cold.
        recovered = expand_multistage(
            engine, comp, p_in_mpa, t_in_k, p_out_mpa, cand.effective_efficiency, cand.stages
        )
        single = expand(engine, comp, p_in_mpa, t_in_k, p_out_mpa, cand.effective_efficiency)
        recovered_kw = mass_flow_kg_s * recovered.specific_work_kj_kg
        aux = expansion_auxiliaries(mass_flow_kg_s, cp, single.outlet_temperature_k, t_in_k)
        preheat_kw = next((a.duty_kw for a in aux if a.kind == "preheating"), 0.0) or 0.0
        cooling_kw = mass_flow_kg_s * cp * max(0.0, t_in_k - single.outlet_temperature_k)

        row = ExpanderComparisonRow(
            tech_id=card.code, name=card.name, category=card.category.value,
            feasible=True, reason="", data_quality=quality,
            effective_efficiency=round(cand.effective_efficiency, 4),
            recovered_power_kw=round(recovered_kw, 3),
            outlet_temperature_k=round(single.outlet_temperature_k, 3),
            preheat_duty_kw=round(preheat_kw, 3),
            cooling_potential_kw=round(cooling_kw, 3),
        )
        if cost is not None:
            row = _with_economics(row, recovered_kw, preheat_kw, cost, co2_kg_per_gj)
        rows.append(row)

    # Rank feasible rows by recovered power (desc); infeasible sink to the bottom.
    rows.sort(key=lambda r: (r.feasible, r.recovered_power_kw or 0.0), reverse=True)
    return rows


def _data_quality(card: DeviceCard) -> str:
    """EXP-CMP-002 — catalog envelopes here are generic families, not a specific unit."""
    return "family"


def _with_economics(
    row: ExpanderComparisonRow,
    recovered_kw: float,
    preheat_kw: float,
    cost: ExpanderCostModel,
    co2_kg_per_gj: float,
) -> ExpanderComparisonRow:
    hours = cost.operating_hours_per_year
    capex = cost.specific_capex_pln_per_kw * recovered_kw
    annual_opex = capex * cost.fixed_opex_pct_per_year
    # Preheat gas consumption offsets useful electrical output value.
    preheat_gj_per_year = preheat_kw / 1000.0 * hours * 3.6 / cost.heater_efficiency
    preheat_co2_t = preheat_gj_per_year * co2_kg_per_gj / 1000.0
    net_kw = max(0.0, recovered_kw)  # gross electrical export; preheat is a heat duty
    annual_energy_mwh = net_kw / 1000.0 * hours
    revenue = annual_energy_mwh * cost.electricity_price_pln_per_mwh
    dcf = DcfInput(
        capex=capex, discount_rate=cost.discount_rate, horizon_years=cost.horizon_years,
        opex_per_year=[annual_opex] * cost.horizon_years,
        revenue_per_year=[revenue] * cost.horizon_years,
        output_per_year=[annual_energy_mwh] * cost.horizon_years,
    )
    result = finance_service.evaluate(dcf, LcoKind.LCOE)
    return ExpanderComparisonRow(
        **{
            **row.__dict__,
            "capex_pln": round(capex, 2),
            "annual_opex_pln": round(annual_opex, 2),
            "annual_energy_mwh": round(annual_energy_mwh, 3),
            "npv_pln": round(result.npv, 2),
            "lcoe_pln_per_mwh": round(result.lco_value, 3) if result.lco_value else None,
            "annual_preheat_co2_t": round(preheat_co2_t, 4),
        }
    )
