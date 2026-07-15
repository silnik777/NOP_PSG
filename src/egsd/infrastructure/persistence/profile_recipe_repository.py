"""Persistence for user composition profiles and versioned blend recipes (OPZ §20)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import BlendRecipeRow, CompositionProfileRow


def _next_version(session: Session, model, code: str) -> int:
    current = session.scalar(select(func.max(model.version)).where(model.code == code))
    return (current or 0) + 1


# ----- Composition profiles ---------------------------------------------------


def save_profile(
    session: Session, *, code: str, name: str, fractions: dict, status: str = "draft",
    owner: str = "system", source: str = "",
) -> CompositionProfileRow:
    version = _next_version(session, CompositionProfileRow, code)
    row = CompositionProfileRow(
        code=code, name=name, version=version, status=status, owner=owner,
        source=source, fractions=fractions,
    )
    session.add(row)
    session.flush()
    return row


def latest_profile(session: Session, code: str) -> CompositionProfileRow | None:
    return session.scalar(
        select(CompositionProfileRow)
        .where(CompositionProfileRow.code == code)
        .order_by(CompositionProfileRow.version.desc())
        .limit(1)
    )


def list_profiles(session: Session) -> list[CompositionProfileRow]:
    # Latest version per code.
    rows = session.scalars(
        select(CompositionProfileRow).order_by(
            CompositionProfileRow.code, CompositionProfileRow.version.desc()
        )
    ).all()
    seen: set[str] = set()
    out: list[CompositionProfileRow] = []
    for r in rows:
        if r.code not in seen:
            seen.add(r.code)
            out.append(r)
    return out


# ----- Blend recipes ----------------------------------------------------------


def save_recipe(
    session: Session, *, code: str, name: str, streams: list, reference_pair: str,
    config_checksum: str, status: str = "draft", owner: str = "system",
) -> BlendRecipeRow:
    version = _next_version(session, BlendRecipeRow, code)
    row = BlendRecipeRow(
        code=code, name=name, version=version, status=status, owner=owner,
        streams=streams, reference_pair=reference_pair, config_checksum=config_checksum,
    )
    session.add(row)
    session.flush()
    return row


def latest_recipe(session: Session, code: str) -> BlendRecipeRow | None:
    return session.scalar(
        select(BlendRecipeRow)
        .where(BlendRecipeRow.code == code)
        .order_by(BlendRecipeRow.version.desc())
        .limit(1)
    )


def list_recipes(session: Session) -> list[BlendRecipeRow]:
    rows = session.scalars(
        select(BlendRecipeRow).order_by(
            BlendRecipeRow.code, BlendRecipeRow.version.desc()
        )
    ).all()
    seen: set[str] = set()
    out: list[BlendRecipeRow] = []
    for r in rows:
        if r.code not in seen:
            seen.add(r.code)
            out.append(r)
    return out
