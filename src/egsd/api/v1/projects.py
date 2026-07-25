"""Project/Variant endpoints + persisting immutable, hashed ResultRecords."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...domain.project.hashing import result_hash
from ...infrastructure.persistence.audit import record_audit
from ...infrastructure.persistence.database import get_session
from ...infrastructure.persistence.models import (
    ProjectRow,
    ReferenceGasProfileRow,
    ResultRecordRow,
    VariantRow,
)

router = APIRouter(prefix="/api/v1", tags=["projects"])


class VariantIn(BaseModel):
    name: str


class ProjectIn(BaseModel):
    name: str
    orgUnit: str = ""
    variants: list[VariantIn] = []


class VariantOut(BaseModel):
    id: int
    name: str
    status: str


class ProjectOut(BaseModel):
    id: int
    name: str
    orgUnit: str
    variants: list[VariantOut]


class ResultRecordIn(BaseModel):
    module: str
    inputs: dict
    outputs: dict
    modelVersions: dict[str, str]
    resultClass: str = "Engineering"


class ResultRecordOut(BaseModel):
    id: int
    recordHash: str
    module: str
    resultClass: str


def _to_out(project: ProjectRow) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        name=project.name,
        orgUnit=project.org_unit,
        variants=[VariantOut(id=v.id, name=v.name, status=v.status) for v in project.variants],
    )


@router.get("/reference-profiles")
def list_reference_profiles(session: Session = Depends(get_session)) -> list[dict]:
    rows = session.scalars(select(ReferenceGasProfileRow)).all()
    return [
        {"code": r.code, "name": r.name, "version": r.version, "fractions": r.fractions}
        for r in rows
    ]


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(body: ProjectIn, session: Session = Depends(get_session)) -> ProjectOut:
    project = ProjectRow(name=body.name, org_unit=body.orgUnit)
    project.variants = [VariantRow(name=v.name) for v in body.variants]
    session.add(project)
    session.flush()
    record_audit(
        session, action="create", object_type="Project", object_id=str(project.id),
        value_after={"name": project.name, "orgUnit": project.org_unit},
    )
    session.commit()
    return _to_out(project)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, session: Session = Depends(get_session)) -> ProjectOut:
    project = session.get(ProjectRow, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return _to_out(project)


@router.post(
    "/variants/{variant_id}/results", response_model=ResultRecordOut, status_code=201
)
def add_result(
    variant_id: int,
    body: ResultRecordIn,
    response: Response,
    session: Session = Depends(get_session),
) -> ResultRecordOut:
    variant = session.get(VariantRow, variant_id)
    if variant is None:
        raise HTTPException(status_code=404, detail="Variant not found")

    record_hash = result_hash(body.inputs, body.modelVersions)
    existing = session.scalar(
        select(ResultRecordRow).where(ResultRecordRow.record_hash == record_hash)
    )
    if existing is not None:
        # Immutable & idempotent: identical inputs+models -> same record (200, not Created).
        response.status_code = 200
        return ResultRecordOut(
            id=existing.id, recordHash=existing.record_hash,
            module=existing.module, resultClass=existing.result_class,
        )

    row = ResultRecordRow(
        variant_id=variant_id,
        record_hash=record_hash,
        module=body.module,
        result_class=body.resultClass,
        inputs=body.inputs,
        outputs=body.outputs,
        model_versions=body.modelVersions,
    )
    session.add(row)
    session.flush()
    record_audit(
        session, action="create", object_type="ResultRecord", object_id=record_hash,
        value_after={"module": body.module},
    )
    session.commit()
    return ResultRecordOut(
        id=row.id, recordHash=row.record_hash, module=row.module, resultClass=row.result_class
    )
