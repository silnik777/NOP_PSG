"""Authentication introspection endpoints (OPZ §37 SEC)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ...config import settings
from ..auth import Principal, current_principal

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class WhoAmIResponse(BaseModel):
    username: str
    role: str
    tier: int
    authEnabled: bool


@router.get("/whoami", response_model=WhoAmIResponse)
def whoami(principal: Principal = Depends(current_principal)) -> WhoAmIResponse:
    return WhoAmIResponse(
        username=principal.username, role=principal.role, tier=principal.tier,
        authEnabled=settings.auth_enabled,
    )
