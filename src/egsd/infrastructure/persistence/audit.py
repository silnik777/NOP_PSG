"""Append-only audit-trail helper (W2.3)."""

from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from .models import AuditLogRow


def session_fingerprint(user_id: str, action: str, object_id: str) -> str:
    raw = f"{user_id}|{action}|{object_id}".encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()[:32]


def record_audit(
    session: Session,
    *,
    action: str,
    object_type: str,
    object_id: str = "",
    user_id: str = "system",
    value_before: dict | None = None,
    value_after: dict | None = None,
) -> AuditLogRow:
    """Insert an immutable audit row. Callers must never update/delete audit rows."""
    row = AuditLogRow(
        user_id=user_id,
        action=action,
        object_type=object_type,
        object_id=object_id,
        value_before=value_before,
        value_after=value_after,
        session_fingerprint=session_fingerprint(user_id, action, object_id),
    )
    session.add(row)
    return row
