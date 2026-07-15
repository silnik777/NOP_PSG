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


class CompositionProfileRow(Base):
    """A user-created, versioned gas composition profile (OPZ §20, MVP #1).

    Distinct from `reference_gas_profiles` (bundled reference data): these are owned,
    status-tracked profiles created/copied by analysts.
    """

    __tablename__ = "composition_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(160))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="draft")  # draft|approved|user
    owner: Mapped[str] = mapped_column(String(128), default="system")
    source: Mapped[str] = mapped_column(String(200), default="")
    fractions: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    __table_args__ = (UniqueConstraint("code", "version", name="uq_profile_code_version"),)


class BlendRecipeRow(Base):
    """A versioned blend recipe (OPZ §20, MVP #5) — a reproducible mixing definition.

    `streams` is a JSON list of {compositionId?|fractions?, share}. The recipe is immutable
    per (code, version); editing creates a new version. `config_checksum` fingerprints the
    inputs so a re-run is verifiably identical.
    """

    __tablename__ = "blend_recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    name: Mapped[str] = mapped_column(String(160))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="draft")
    owner: Mapped[str] = mapped_column(String(128), default="system")
    streams: Mapped[list] = mapped_column(JSON)
    reference_pair: Mapped[str] = mapped_column(String(8), default="25/0")
    config_checksum: Mapped[str] = mapped_column(String(80), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    __table_args__ = (UniqueConstraint("code", "version", name="uq_recipe_code_version"),)


class PriceSeriesRow(Base):
    """Metadata for a market price series (e.g. PL gas TGE, EU ETS)."""

    __tablename__ = "price_series"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    unit: Mapped[str] = mapped_column(String(32))  # e.g. PLN/MWh, EUR/t
    currency: Mapped[str] = mapped_column(String(8))
    source: Mapped[str] = mapped_column(String(128), default="")
    version: Mapped[str] = mapped_column(String(32), default="1.0.0")


class PricePointRow(Base):
    """A dated observation in a price series (append-only history)."""

    __tablename__ = "price_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    series_code: Mapped[str] = mapped_column(String(64), index=True)
    observed_on: Mapped[str] = mapped_column(String(10))  # ISO date YYYY-MM-DD
    value: Mapped[float] = mapped_column()
    __table_args__ = (UniqueConstraint("series_code", "observed_on", name="uq_series_date"),)


class MacroScenarioRow(Base):
    """A named macro price scenario sourced from an institutional report family."""

    __tablename__ = "macro_scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    family: Mapped[str] = mapped_column(String(32))  # low | base | high
    source: Mapped[str] = mapped_column(String(200))  # report attribution
    vintage: Mapped[str] = mapped_column(String(16), default="")  # publication year
    notes: Mapped[str] = mapped_column(Text, default="")


class MacroScenarioPointRow(Base):
    """Annual projected price for a (scenario, commodity, year)."""

    __tablename__ = "macro_scenario_points"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_code: Mapped[str] = mapped_column(String(64), index=True)
    commodity_code: Mapped[str] = mapped_column(String(64))  # matches price_series.code
    year: Mapped[int] = mapped_column(Integer)
    value: Mapped[float] = mapped_column()
    __table_args__ = (
        UniqueConstraint(
            "scenario_code", "commodity_code", "year", name="uq_macro_point"
        ),
    )


class DeviceCardRow(Base):
    """Compressor/expander technology card (reference data)."""

    __tablename__ = "device_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16))  # Compressor | Expander
    category: Mapped[str] = mapped_column(String(32))
    stage_ratio_min: Mapped[float] = mapped_column()
    stage_ratio_max: Mapped[float] = mapped_column()
    stage_ratio_optimal: Mapped[float] = mapped_column()
    isentropic_efficiency_nominal: Mapped[float] = mapped_column()
    ratio_derate: Mapped[float] = mapped_column()
    mass_flow_min_kg_s: Mapped[float] = mapped_column()
    mass_flow_max_kg_s: Mapped[float] = mapped_column()
    max_discharge_temperature_k: Mapped[float] = mapped_column(default=473.15)
    notes: Mapped[str] = mapped_column(Text, default="")


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
