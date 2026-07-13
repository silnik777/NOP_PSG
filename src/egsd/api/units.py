"""Unit conversion for API inputs (pressure -> MPa, temperature -> K)."""

from __future__ import annotations

_PRESSURE_TO_MPA: dict[str, float] = {
    "MPa": 1.0,
    "kPa": 1e-3,
    "Pa": 1e-6,
    "bar": 0.1,
    "barg": 0.1,  # treated as bar for the skeleton (gauge offset handled upstream)
    "psi": 0.00689476,
}


def pressure_to_mpa(value: float, unit: str) -> float:
    try:
        return value * _PRESSURE_TO_MPA[unit]
    except KeyError as exc:
        raise ValueError(f"Unsupported pressure unit {unit!r}") from exc


def temperature_to_k(value: float, unit: str) -> float:
    if unit == "K":
        return value
    if unit in ("degC", "C", "°C"):
        return value + 273.15
    raise ValueError(f"Unsupported temperature unit {unit!r}")


def mass_flow_to_kg_s(value: float, unit: str) -> float:
    if unit == "kg/s":
        return value
    if unit == "kg/h":
        return value / 3600.0
    if unit == "t/h":
        return value * 1000.0 / 3600.0
    raise ValueError(f"Unsupported mass-flow unit {unit!r}")
