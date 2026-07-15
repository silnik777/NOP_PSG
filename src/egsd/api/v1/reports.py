"""Technical report endpoints (OPZ §33, MVP #23)."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from ...application.report_service import ReportBlock, TechnicalReport, build_report

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


class ReportBlockDTO(BaseModel):
    title: str
    resultClass: str = "engineering"
    inputs: dict = Field(default_factory=dict)
    outputs: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    modelVersions: dict[str, str] = Field(default_factory=dict)


class TechnicalReportRequest(BaseModel):
    title: str = "Raport techniczny"
    project: str = ""
    variant: str = ""
    scenario: str = ""
    author: str = "system"
    blocks: list[ReportBlockDTO]


class TechnicalReportResponse(BaseModel):
    configChecksum: str
    html: str


def _to_report(req: TechnicalReportRequest) -> TechnicalReport:
    return TechnicalReport(
        title=req.title, project=req.project, variant=req.variant, scenario=req.scenario,
        author=req.author,
        blocks=[
            ReportBlock(
                title=b.title, result_class=b.resultClass, inputs=b.inputs,
                outputs=b.outputs, warnings=b.warnings, model_versions=b.modelVersions,
            )
            for b in req.blocks
        ],
    )


@router.post("/technical", response_model=TechnicalReportResponse)
def technical_report_json(req: TechnicalReportRequest) -> TechnicalReportResponse:
    """Return the report HTML plus its config checksum (for storage/embedding)."""
    doc, checksum = build_report(_to_report(req))
    return TechnicalReportResponse(configChecksum=checksum, html=doc)


@router.post("/technical.html", response_class=HTMLResponse)
def technical_report_html(req: TechnicalReportRequest) -> HTMLResponse:
    """Return the report as a ready-to-view / printable HTML document."""
    doc, _ = build_report(_to_report(req))
    return HTMLResponse(content=doc)
