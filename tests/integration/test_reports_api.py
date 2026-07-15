"""API tests for the technical report generator (OPZ §33, MVP #23)."""

from __future__ import annotations


def _body() -> dict:
    return {
        "title": "Raport wariantu A", "project": "P-1", "variant": "W-1",
        "scenario": "BASE", "author": "analityk",
        "blocks": [
            {"title": "Spalanie i emisje", "resultClass": "engineering",
             "inputs": {"metan": 0.95, "propan": 0.05},
             "outputs": {"co2KgPerGjInput": 50.24},
             "warnings": ["dane ilustracyjne"], "modelVersions": {"combustion": "1.0.0"}},
            {"title": "Ekspansja (screening)", "resultClass": "screening",
             "inputs": {"pIn": 5.0}, "outputs": {"recoveredKw": 2700}},
        ],
    }


def test_technical_report_json(client):
    r = client.post("/api/v1/reports/technical", json=_body())
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["configChecksum"].startswith("sha256:")
    assert "<title>Raport wariantu A</title>" in d["html"]
    assert "Suma kontrolna" in d["html"]
    # Quality class badges and the screening caveat are present.
    assert "screening" in d["html"]
    assert "screeningowy" in d["html"]  # footer caveat (§7)


def test_report_checksum_is_deterministic(client):
    a = client.post("/api/v1/reports/technical", json=_body()).json()["configChecksum"]
    b = client.post("/api/v1/reports/technical", json=_body()).json()["configChecksum"]
    assert a == b


def test_report_html_endpoint(client):
    r = client.post("/api/v1/reports/technical.html", json=_body())
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert b"<!doctype html>" in r.content.lower()
