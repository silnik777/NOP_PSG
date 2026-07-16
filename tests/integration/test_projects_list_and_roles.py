"""Project listing, embedded results, and role-guarded creation."""

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


def test_list_projects_empty_then_populated(client):
    assert client.get("/api/v1/projects").json() == []
    client.post("/api/v1/projects", json={"name": "P1", "orgUnit": "R&D",
                                          "variants": [{"name": "W1"}]})
    rows = client.get("/api/v1/projects").json()
    assert len(rows) == 1
    assert rows[0]["name"] == "P1"
    assert rows[0]["variants"][0]["name"] == "W1"
    assert rows[0]["variants"][0]["results"] == []


def test_project_detail_includes_results(client):
    pr = client.post("/api/v1/projects", json={"name": "P", "variants": [{"name": "W"}]}).json()
    vid = pr["variants"][0]["id"]
    client.post(f"/api/v1/variants/{vid}/results", json={
        "module": "combustion", "inputs": {"methane": 1.0}, "outputs": {"co2": 50},
        "modelVersions": {"combustion": "1.0.0"},
    })
    detail = client.get(f"/api/v1/projects/{pr['id']}").json()
    results = detail["variants"][0]["results"]
    assert len(results) == 1
    assert results[0]["module"] == "combustion"
    assert results[0]["recordHash"].startswith("sha256:")


def test_create_project_requires_role_when_auth_on(client, auth_on):
    body = {"name": "P", "variants": []}
    assert client.post("/api/v1/projects", json=body).status_code == 401
    assert client.post("/api/v1/projects", json=body,
                       headers={"Authorization": "Bearer dev-viewer"}).status_code == 403
    assert client.post("/api/v1/projects", json=body,
                       headers={"Authorization": "Bearer dev-analyst"}).status_code == 201
    # Listing stays open (read).
    assert client.get("/api/v1/projects").status_code == 200
