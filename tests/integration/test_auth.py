"""Tests for the minimal role-based auth (OPZ §37 SEC). Default-off, enabled per test."""

from __future__ import annotations

import pytest

from egsd.config import settings


@pytest.fixture()
def auth_on():
    settings.auth_enabled = True
    try:
        yield
    finally:
        settings.auth_enabled = False


def test_auth_disabled_by_default(client):
    r = client.get("/api/v1/auth/whoami")
    assert r.status_code == 200
    d = r.json()
    assert d["authEnabled"] is False
    assert d["role"] == "sysadmin"  # anonymous dev principal


def test_disabled_auth_allows_writes(client):
    r = client.post("/api/v1/gas/profiles",
                    json={"name": "T", "gasComposition": {"methane": 1.0}})
    assert r.status_code == 201


def test_enabled_requires_token(client, auth_on):
    assert client.get("/api/v1/auth/whoami").status_code == 401


def test_enabled_resolves_principal(client, auth_on):
    r = client.get("/api/v1/auth/whoami", headers={"Authorization": "Bearer dev-analyst"})
    assert r.status_code == 200
    assert r.json()["role"] == "analyst"
    assert r.json()["tier"] == 2


def test_enabled_role_enforced_on_write(client, auth_on):
    hdr_viewer = {"Authorization": "Bearer dev-viewer"}
    hdr_analyst = {"Authorization": "Bearer dev-analyst"}
    body = {"name": "T", "gasComposition": {"methane": 1.0}}
    assert client.post("/api/v1/gas/profiles", json=body).status_code == 401  # no token
    assert client.post("/api/v1/gas/profiles", json=body,
                       headers=hdr_viewer).status_code == 403  # insufficient role
    assert client.post("/api/v1/gas/profiles", json=body,
                       headers=hdr_analyst).status_code == 201


def test_enabled_keeps_compute_endpoints_open(client, auth_on):
    # Read/compute endpoints are not role-guarded (decision support stays accessible).
    r = client.post("/api/v1/gas/quality-check", json={"gasComposition": {"methane": 1.0}})
    assert r.status_code == 200
    assert client.post("/api/v1/combustion/emissions",
                       json={"gasComposition": {"methane": 1.0}}).status_code == 200


def test_invalid_token_rejected(client, auth_on):
    assert client.get("/api/v1/auth/whoami",
                      headers={"Authorization": "Bearer nonsense"}).status_code == 401
