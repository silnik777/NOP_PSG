"""Export endpoints: engineering results to CSV/XLSX (OPZ MVP §10.2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ...application.compression_service import CompressionService
from ...application.hydraulics_service import HydraulicsService
from ...domain.gas.composition import CompositionError
from ...domain.thermo.compression import CompressionInput
from ...infrastructure.export.writers import (
    ExportDocument,
    ExportRow,
    to_csv_bytes,
    to_xlsx_bytes,
)
from ...infrastructure.gas_engine.errors import EngineError
from ...infrastructure.persistence.database import get_session
from ..units import (
    length_to_m,
    mass_flow_to_kg_s,
    normal_flow_to_nm3_h,
    pressure_to_mpa,
    temperature_to_k,
)
from .common import resolve_composition
from .schemas import CompressionRequest, HydraulicsRequest

router = APIRouter(prefix="/api/v1/export", tags=["export"])

_compression = CompressionService()
_hydraulics = HydraulicsService()

_MEDIA = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _render(doc: ExportDocument, fmt: str, filename_stem: str) -> Response:
    if fmt not in _MEDIA:
        raise HTTPException(status_code=422, detail="format must be 'csv' or 'xlsx'")
    body = to_csv_bytes(doc) if fmt == "csv" else to_xlsx_bytes(doc)
    return Response(
        content=body,
        media_type=_MEDIA[fmt],
        headers={"Content-Disposition": f'attachment; filename="{filename_stem}.{fmt}"'},
    )


@router.post("/compression")
def export_compression(
    req: CompressionRequest,
    fmt: str = Query("xlsx", alias="format"),
    session: Session = Depends(get_session),
) -> Response:
    try:
        composition = resolve_composition(req.compositionId, req.gasComposition, session)
        data = CompressionInput(
            composition=composition,
            mass_flow_kg_s=mass_flow_to_kg_s(req.massFlowRate.value, req.massFlowRate.unit),
            inlet_pressure_mpa=pressure_to_mpa(req.inletPressure.value, req.inletPressure.unit),
            inlet_temperature_k=temperature_to_k(
                req.inletTemperature.value, req.inletTemperature.unit
            ),
            outlet_pressure_mpa=pressure_to_mpa(
                req.outletPressureTarget.value, req.outletPressureTarget.unit
            ),
            isentropic_efficiency=req.isentropicEfficiency,
            mechanical_efficiency=req.mechanicalEfficiency,
        )
        result = _compression.calculate(data)
    except (CompositionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EngineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    doc = ExportDocument(
        title="Module I — Compression",
        result_class=result.result_class.value,
        rows=[
            ExportRow("Required shaft power", round(result.required_shaft_power_kw, 3), "kW"),
            ExportRow("Outlet temperature", round(result.outlet_temperature_k, 3), "K"),
            ExportRow("Polytropic head", round(result.polytropic_head_kj_kg, 3), "kJ/kg"),
            ExportRow("Isentropic head", round(result.isentropic_head_kj_kg, 3), "kJ/kg"),
            ExportRow("Validation status", result.validation_status.value),
        ],
        warnings=list(result.warnings),
    )
    return _render(doc, fmt, "compression")


@router.post("/hydraulics")
def export_hydraulics(
    req: HydraulicsRequest,
    fmt: str = Query("xlsx", alias="format"),
    session: Session = Depends(get_session),
) -> Response:
    from ...domain.hydraulics.models import HydraulicsInput

    try:
        composition = resolve_composition(req.compositionId, req.gasComposition, session)
        data = HydraulicsInput(
            composition=composition,
            diameter_m=length_to_m(req.diameter.value, req.diameter.unit),
            roughness_m=length_to_m(req.roughness.value, req.roughness.unit),
            length_m=length_to_m(req.length.value, req.length.unit),
            inlet_pressure_mpa=pressure_to_mpa(req.inletPressure.value, req.inletPressure.unit),
            gas_temperature_k=temperature_to_k(req.gasTemperature.value, req.gasTemperature.unit),
            normal_flow_nm3_h=normal_flow_to_nm3_h(req.normalFlow.value, req.normalFlow.unit),
        )
        result = _hydraulics.steady_flow(data)
    except (CompositionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except EngineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    doc = ExportDocument(
        title="Module II — Hydraulics (steady flow)",
        result_class=result.result_class.value,
        rows=[
            ExportRow("Outlet pressure", round(result.outlet_pressure_mpa, 5), "MPa"),
            ExportRow("Pressure drop", round(result.pressure_drop_mpa, 5), "MPa"),
            ExportRow("Mass flow", round(result.mass_flow_kg_s, 4), "kg/s"),
            ExportRow("Average velocity", round(result.average_velocity_m_s, 4), "m/s"),
            ExportRow("Reynolds number", round(result.reynolds_number, 1), "-"),
            ExportRow("Friction factor (Darcy)", round(result.friction_factor, 6), "-"),
            ExportRow("Flow regime", result.flow_regime.value),
            ExportRow("Mach number", round(result.mach_number, 5), "-"),
            ExportRow("Validation status", result.validation_status.value),
        ],
        warnings=list(result.warnings),
    )
    return _render(doc, fmt, "hydraulics")
