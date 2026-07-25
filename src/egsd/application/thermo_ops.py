"""Reusable isentropic-efficiency compression/expansion primitives.

Both use the GasPropertyEngine as the single source of thermodynamic states, mirroring the
method already validated in CompressionService (Module I).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..domain.gas.composition import GasComposition
from ..infrastructure.gas_engine.coolprop_engine import CoolPropGasEngine

_T_SPAN_K = 500.0


@dataclass(frozen=True)
class WorkResult:
    specific_work_kj_kg: float  # >0: work in (compression) or work out (expansion)
    outlet_temperature_k: float
    isentropic_delta_kj_kg: float


def compress(
    engine: CoolPropGasEngine,
    comp: GasComposition,
    p_in_mpa: float,
    t_in_k: float,
    p_out_mpa: float,
    eta_isentropic: float,
) -> WorkResult:
    inlet = engine.point_properties(comp, p_in_mpa, t_in_k).state
    h_in, s_in = inlet.enthalpy_kj_kg, inlet.entropy_kj_kgk
    t_out_s = engine.temperature_at_ps(comp, p_out_mpa, s_in, t_in_k, t_in_k + _T_SPAN_K)
    h_out_s = engine.enthalpy_kj_kg(comp, p_out_mpa, t_out_s)
    isentropic = h_out_s - h_in
    actual = isentropic / eta_isentropic
    h_out = h_in + actual
    t_out = engine.temperature_at_ph(comp, p_out_mpa, h_out, t_in_k, t_in_k + _T_SPAN_K)
    return WorkResult(actual, t_out, isentropic)


def expand(
    engine: CoolPropGasEngine,
    comp: GasComposition,
    p_in_mpa: float,
    t_in_k: float,
    p_out_mpa: float,
    eta_isentropic: float,
) -> WorkResult:
    inlet = engine.point_properties(comp, p_in_mpa, t_in_k).state
    h_in, s_in = inlet.enthalpy_kj_kg, inlet.entropy_kj_kgk
    t_low = max(60.0, t_in_k - _T_SPAN_K)
    t_out_s = engine.temperature_at_ps(comp, p_out_mpa, s_in, t_low, t_in_k + 5.0)
    h_out_s = engine.enthalpy_kj_kg(comp, p_out_mpa, t_out_s)
    isentropic_drop = h_in - h_out_s
    actual_work = isentropic_drop * eta_isentropic
    h_out = h_in - actual_work
    t_out = engine.temperature_at_ph(comp, p_out_mpa, h_out, t_low, t_in_k + 5.0)
    return WorkResult(actual_work, t_out, isentropic_drop)


def compress_multistage(
    engine: CoolPropGasEngine,
    comp: GasComposition,
    p_in_mpa: float,
    intercool_t_k: float,
    p_out_mpa: float,
    eta_isentropic: float,
    stages: int,
) -> WorkResult:
    """Total specific work for `stages` equal-ratio stages, intercooled to `intercool_t_k`."""
    ratio = (p_out_mpa / p_in_mpa) ** (1.0 / stages)
    total = 0.0
    t_out = intercool_t_k
    p = p_in_mpa
    for i in range(stages):
        p_next = p_out_mpa if i == stages - 1 else p * ratio
        stage = compress(engine, comp, p, intercool_t_k, p_next, eta_isentropic)
        total += stage.specific_work_kj_kg
        t_out = stage.outlet_temperature_k
        p = p_next
    return WorkResult(total, t_out, total * eta_isentropic)


def expand_multistage(
    engine: CoolPropGasEngine,
    comp: GasComposition,
    p_in_mpa: float,
    reheat_t_k: float,
    p_out_mpa: float,
    eta_isentropic: float,
    stages: int,
) -> WorkResult:
    """Total specific work out for `stages` equal-ratio stages, reheated to `reheat_t_k`."""
    ratio = (p_out_mpa / p_in_mpa) ** (1.0 / stages)
    total = 0.0
    t_out = reheat_t_k
    p = p_in_mpa
    for i in range(stages):
        p_next = p_out_mpa if i == stages - 1 else p * ratio
        stage = expand(engine, comp, p, reheat_t_k, p_next, eta_isentropic)
        total += stage.specific_work_kj_kg
        t_out = stage.outlet_temperature_k
        p = p_next
    return WorkResult(total, t_out, total / eta_isentropic)
