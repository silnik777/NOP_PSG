"""Select the optimal compressor/expander technology and its auxiliaries.

Given a duty (pressure ratio, mass flow, gas, temperatures) the service:
  1. filters catalog cards feasible by flow,
  2. computes the required stage count and per-stage ratio for each,
  3. scores effective isentropic efficiency from the technology characteristic,
  4. ranks candidates and picks the best,
  5. proposes auxiliaries: inter/after-cooling for compression, pre-heating for expansion,
     and a pressure-reducer split when a single machine cannot meet the target pressure.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..domain.devices.models import DeviceCard, MachineRole

# Temperature guards.
PIPE_COATING_MAX_K = 323.15  # 50 degC — protect pipeline coating after compression
HYDRATE_GUARD_MIN_K = 273.15  # 0 degC — avoid hydrates/ground freezing after expansion


@dataclass(frozen=True)
class DutySpec:
    overall_ratio: float  # p_out/p_in (compressor) or p_in/p_out (expander)
    mass_flow_kg_s: float
    role: MachineRole


@dataclass(frozen=True)
class AuxiliaryProposal:
    kind: str  # "aftercooling" | "intercooling" | "preheating" | "pressure_reducer"
    description: str
    duty_kw: float | None = None
    source: str | None = None


@dataclass(frozen=True)
class DeviceCandidate:
    card: DeviceCard
    stages: int
    stage_ratio: float
    effective_efficiency: float
    feasible: bool
    reason: str = ""


@dataclass(frozen=True)
class SelectionResult:
    selected: DeviceCandidate | None
    ranked: list[DeviceCandidate]
    auxiliaries: list[AuxiliaryProposal] = field(default_factory=list)


def evaluate(card: DeviceCard, duty: DutySpec) -> DeviceCandidate:
    if card.role != duty.role:
        return DeviceCandidate(card, 0, 0.0, 0.0, False, "wrong role")
    if not card.accepts_flow(duty.mass_flow_kg_s):
        return DeviceCandidate(
            card, 0, 0.0, 0.0, False,
            f"flow {duty.mass_flow_kg_s:.2f} kg/s outside "
            f"[{card.mass_flow_min_kg_s}, {card.mass_flow_max_kg_s}] kg/s",
        )
    stages = card.stages_for(duty.overall_ratio)
    stage_ratio = duty.overall_ratio ** (1.0 / stages)
    eff = card.efficiency_at(stage_ratio)
    if eff <= 0:
        return DeviceCandidate(card, stages, stage_ratio, 0.0, False, "ratio outside envelope")
    return DeviceCandidate(card, stages, stage_ratio, eff, True)


def select(
    cards: list[DeviceCard], duty: DutySpec
) -> tuple[DeviceCandidate | None, list[DeviceCandidate]]:
    ranked = sorted(
        (evaluate(c, duty) for c in cards),
        key=lambda x: (x.feasible, x.effective_efficiency, -x.stages),
        reverse=True,
    )
    feasible = [c for c in ranked if c.feasible]
    return (feasible[0] if feasible else None), ranked


def compression_auxiliaries(
    stages: int,
    mass_flow_kg_s: float,
    cp_kj_kgk: float,
    discharge_temperature_k: float,
    coolant_approach_k: float = 288.15 + 10.0,  # air-cooled target ~ ambient + approach
) -> list[AuxiliaryProposal]:
    aux: list[AuxiliaryProposal] = []
    if stages > 1:
        aux.append(
            AuxiliaryProposal(
                "intercooling",
                f"{stages - 1} chłodnica(-e) międzystopniowa(-e) — schłodzenie do temperatury "
                "ssania między stopniami.",
                source="air-cooler / water-cooler",
            )
        )
    if discharge_temperature_k > PIPE_COATING_MAX_K:
        target = PIPE_COATING_MAX_K
        duty_kw = mass_flow_kg_s * cp_kj_kgk * (discharge_temperature_k - target)
        source = "air-cooler" if target >= coolant_approach_k else "water/chilled-cooler"
        aux.append(
            AuxiliaryProposal(
                "aftercooling",
                f"Chłodnica końcowa: schłodzić z {discharge_temperature_k:.1f} K do "
                f"{target:.1f} K (ochrona powłoki gazociągu, T_max 50°C).",
                duty_kw=duty_kw, source=source,
            )
        )
    return aux


def expansion_auxiliaries(
    mass_flow_kg_s: float,
    cp_kj_kgk: float,
    outlet_temperature_k: float,
    inlet_temperature_k: float,
) -> list[AuxiliaryProposal]:
    aux: list[AuxiliaryProposal] = []
    if outlet_temperature_k < HYDRATE_GUARD_MIN_K:
        # Pre-heat inlet enough to lift the outlet above the hydrate/freeze guard.
        delta = HYDRATE_GUARD_MIN_K - outlet_temperature_k
        duty_kw = mass_flow_kg_s * cp_kj_kgk * delta
        aux.append(
            AuxiliaryProposal(
                "preheating",
                f"Podgrzew wstępny gazu przed ekspansją (efekt Joule'a-Thomsona/ekspansji): "
                f"wylot {outlet_temperature_k:.1f} K < 273.15 K grozi hydratami/zamarzaniem; "
                f"podnieść wlot o ~{delta:.1f} K.",
                duty_kw=duty_kw,
                source="gas-fired heater / waste-heat / electric",
            )
        )
    return aux


def reducer_split(
    inlet_pressure_mpa: float,
    target_pressure_mpa: float,
    machine_outlet_pressure_mpa: float,
    role: MachineRole,
) -> AuxiliaryProposal | None:
    """Advise a throttle reducer in series when the machine does not reach the target pressure."""
    if role != MachineRole.EXPANDER:
        return None
    if machine_outlet_pressure_mpa > target_pressure_mpa + 1e-6:
        return AuxiliaryProposal(
            "pressure_reducer",
            f"Reduktor dławiący ZA ekspanderem: dobicie redukcji z "
            f"{machine_outlet_pressure_mpa:.3f} MPa do {target_pressure_mpa:.3f} MPa.",
        )
    return None
