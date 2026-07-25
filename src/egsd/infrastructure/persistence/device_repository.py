"""Load device cards from the catalog into domain objects."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...domain.devices.models import DeviceCard, DeviceCategory, MachineRole
from .models import DeviceCardRow


def _to_domain(row: DeviceCardRow) -> DeviceCard:
    return DeviceCard(
        code=row.code,
        name=row.name,
        role=MachineRole(row.role),
        category=DeviceCategory(row.category),
        stage_ratio_min=row.stage_ratio_min,
        stage_ratio_max=row.stage_ratio_max,
        stage_ratio_optimal=row.stage_ratio_optimal,
        isentropic_efficiency_nominal=row.isentropic_efficiency_nominal,
        ratio_derate=row.ratio_derate,
        mass_flow_min_kg_s=row.mass_flow_min_kg_s,
        mass_flow_max_kg_s=row.mass_flow_max_kg_s,
        max_discharge_temperature_k=row.max_discharge_temperature_k,
        notes=row.notes,
    )


def list_device_cards(session: Session, role: MachineRole | None = None) -> list[DeviceCard]:
    stmt = select(DeviceCardRow)
    if role is not None:
        stmt = stmt.where(DeviceCardRow.role == role.value)
    return [_to_domain(r) for r in session.scalars(stmt).all()]


def get_device_card(session: Session, code: str) -> DeviceCard | None:
    row = session.scalar(select(DeviceCardRow).where(DeviceCardRow.code == code))
    return _to_domain(row) if row else None
