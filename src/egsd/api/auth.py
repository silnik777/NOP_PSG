"""Minimal role-based authentication (OPZ §37 SEC, roles §10).

A deliberately small, self-contained bearer-token mechanism so the platform can enforce the
role model today, with corporate SSO (SAML/OIDC/AD) as the target integration (ZP-002). It is
disabled by default (`EGSD_AUTH_ENABLED=false`) so the open dev/test skeleton is unaffected;
when enabled, protected routes require `Authorization: Bearer <token>` mapping to a principal
whose role tier meets the route's minimum.

The bundled token→principal map is illustrative and MUST be replaced by the identity provider
before production. Tokens are read from the environment when provided.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException

from ..config import settings

# OPZ §10 roles mapped onto an ordered privilege tier.
ROLE_TIER: dict[str, int] = {
    "viewer": 1,        # użytkownik (odczyt)
    "analyst": 2,       # analityk
    "reviewer": 3,      # recenzent
    "approver": 4,      # zatwierdzający
    "data_admin": 5,    # administrator danych
    "model_admin": 5,   # administrator modeli
    "sysadmin": 6,      # administrator systemu
    "auditor": 2,       # audytor (odczyt śladu, bez modyfikacji)
}


@dataclass(frozen=True)
class Principal:
    username: str
    role: str

    @property
    def tier(self) -> int:
        return ROLE_TIER.get(self.role, 0)


def _token_map() -> dict[str, Principal]:
    """Bundled illustrative tokens; override any via env (EGSD_TOKEN_<ROLE>)."""
    base = {
        "dev-viewer": Principal("viewer", "viewer"),
        "dev-analyst": Principal("analyst", "analyst"),
        "dev-approver": Principal("approver", "approver"),
        "dev-admin": Principal("admin", "sysadmin"),
    }
    out = dict(base)
    for role in ("viewer", "analyst", "approver", "sysadmin"):
        env = os.environ.get(f"EGSD_TOKEN_{role.upper()}")
        if env:
            out[env] = Principal(role, role)
    return out


_ANON = Principal("anonymous", "sysadmin")  # auth disabled -> full access in dev


def current_principal(authorization: str | None = Header(default=None)) -> Principal:
    """Resolve the caller. When auth is disabled, everyone is an anonymous sysadmin (dev)."""
    if not settings.auth_enabled:
        return _ANON
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Wymagany token (Authorization: Bearer).")
    token = authorization.split(" ", 1)[1].strip()
    principal = _token_map().get(token)
    if principal is None:
        raise HTTPException(status_code=401, detail="Nieprawidłowy token.")
    return principal


def require_role(min_role: str):
    """Dependency factory: require the caller's role tier to meet `min_role`."""
    needed = ROLE_TIER[min_role]

    def _guard(principal: Principal = Depends(current_principal)) -> Principal:
        if principal.tier < needed:
            raise HTTPException(
                status_code=403,
                detail=f"Rola '{principal.role}' nie ma uprawnień (wymagane ≥ '{min_role}').",
            )
        return principal

    return _guard
