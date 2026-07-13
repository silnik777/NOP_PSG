"""SQLAlchemy ORM models.

Design constraints from the OPZ:
- ResultRecord is immutable and identified by a SHA-256 hash (no updates).
- AuditLog is append-only (W2.3): timestamp UTC, user, object, before/after, session hash.
- Variants carry SION status (Reference vs Simulation).
Portable column types are used so the same schema runs on SQLite (dev) and PostgreSQL (prod).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ModelVersionRow(Base):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(64))
    version: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (UniqueConstraint("key", "version", name="uq_model_key_version"),)


class ReferenceGasProfileRow(Base):
    __tablename__ = "reference_gas_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    version: Mapped[str] = mapped_column(String(32), default="1.0.0")
    fractions: Mapped[dict] = mapped_column(JSON)


class ProjectRow(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(256))
    org_unit: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    variants: Mapped[list[VariantRow]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class VariantRow(Base):
    __tablename__ = "variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(32), default="Reference")
    overrides: Mapped[dict] = mapped_column(JSON, default=dict)

    project: Mapped[ProjectRow] = relationship(back_populates="variants")
    results: Mapped[list[ResultRecordRow]] = relationship(
        back_populates="variant", cascade="all, delete-orphan"
    )


class ResultRecordRow(Base):
    """Immutable calculation output — never updated in place."""

    __tablename__ = "result_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("variants.id"))
    record_hash: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    module: Mapped[str] = mapped_column(String(64))
    result_class: Mapped[str] = mapped_column(String(32), default="Engineering")
    inputs: Mapped[dict] = mapped_column(JSON)
    outputs: Mapped[dict] = mapped_column(JSON)
    model_versions: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    variant: Mapped[VariantRow] = relationship(back_populates="results")


class AuditLogRow(Base):
    """Append-only audit trail (W2.3). Rows are inserted, never updated or deleted."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    user_id: Mapped[str] = mapped_column(String(128), default="system")
    action: Mapped[str] = mapped_column(String(64))
    object_type: Mapped[str] = mapped_column(String(64))
    object_id: Mapped[str] = mapped_column(String(128), default="")
    value_before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    value_after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    session_fingerprint: Mapped[str] = mapped_column(String(80), default="")
