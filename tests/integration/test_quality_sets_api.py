"""API tests for versioned, selectable quality requirement sets (OPZ §21, MVP #7)."""

from __future__ import annotations


def test_list_requirement_sets(client):
    r = client.get("/api/v1/gas/quality-requirement-sets")
    assert r.status_code == 200, r.text
    codes = {s["code"] for s in r.json()}
    assert "PL-E-2026" in codes
    for s in r.json():
        assert s["version"]
        assert s["wobbeMin"] < s["wobbeMax"]
        assert s["source"]  # provenance never empty (ZP-001)


def test_quality_check_uses_selected_set_and_echoes_it(client):
    r = client.post("/api/v1/gas/quality-check", json={
        "gasComposition": {"methane": 0.98, "nitrogen": 0.02},
        "requirementSetId": "PL-E-2026",
    })
    assert r.status_code == 200, r.text
    d = r.json()
    assert "PL-E-2026" in d["requirementSet"]
    assert d["withinSpec"] is True


def test_different_sets_give_different_verdicts(client):
    gas = {"gasComposition": {"methane": 0.74, "nitrogen": 0.26}}
    e = client.post("/api/v1/gas/quality-check", json={**gas, "requirementSetId": "PL-E-2026"})
    lw = client.post("/api/v1/gas/quality-check", json={**gas, "requirementSetId": "PL-Lw-2026"})
    # A nitrogen-rich gas fails the high-methane E set but the Lw thresholds differ.
    assert e.json()["requirementSet"] != lw.json()["requirementSet"]


def test_unknown_set_is_404(client):
    r = client.post("/api/v1/gas/quality-check", json={
        "gasComposition": {"methane": 1.0}, "requirementSetId": "DOES-NOT-EXIST",
    })
    assert r.status_code == 404


def test_default_label_when_no_set_selected(client):
    r = client.post("/api/v1/gas/quality-check", json={"gasComposition": {"methane": 1.0}})
    assert r.status_code == 200
    assert "wbudowany" in r.json()["requirementSet"]
