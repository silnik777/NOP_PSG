"""API tests for own gas profiles and versioned blend recipes (OPZ §20, MVP #1, #5)."""

from __future__ import annotations


def test_create_and_list_own_profile(client):
    r = client.post("/api/v1/gas/profiles", json={
        "name": "Biometan surowy", "status": "user", "source": "pomiar",
        "gasComposition": {"methane": 0.62, "carbon_dioxide": 0.36, "nitrogen": 0.02},
    })
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["version"] == 1
    assert abs(sum(d["fractions"].values()) - 1.0) < 1e-6  # normalized
    codes = {p["code"] for p in client.get("/api/v1/gas/profiles").json()}
    assert d["code"] in codes


def test_profile_usable_as_composition_id(client):
    code = client.post("/api/v1/gas/profiles", json={
        "name": "Profil testowy",
        "gasComposition": {"methane": 0.9, "ethane": 0.1},
    }).json()["code"]
    # The saved profile resolves as a compositionId in other endpoints.
    r = client.post("/api/v1/combustion/emissions", json={"compositionId": code})
    assert r.status_code == 200, r.text
    assert r.json()["co2KgPerGjInput"] > 0


def test_recipe_versioning_and_deterministic_rerun(client):
    prof = client.post("/api/v1/gas/profiles", json={
        "name": "Wsad", "gasComposition": {"methane": 0.6, "carbon_dioxide": 0.4},
    }).json()["code"]
    body = {"name": "Receptura A", "streams": [
        {"compositionId": prof, "share": 0.5},
        {"compositionId": "REF-GAS-E", "share": 0.5},
    ]}
    r1 = client.post("/api/v1/gas/recipes", json=body)
    assert r1.status_code == 201, r1.text
    code = r1.json()["code"]
    assert r1.json()["version"] == 1
    assert r1.json()["configChecksum"].startswith("sha256:")

    # Re-running the same recipe is byte-for-byte identical.
    a = client.post(f"/api/v1/gas/recipes/{code}/run")
    b = client.post(f"/api/v1/gas/recipes/{code}/run")
    assert a.status_code == 200, a.text
    assert a.json()["composition"] == b.json()["composition"]
    assert a.json()["configChecksum"] == b.json()["configChecksum"]
    assert a.json()["wobbeIndex"]["value"] > 0

    # Saving under the same code creates a new version (immutability of prior version).
    r2 = client.post("/api/v1/gas/recipes", json={**body, "code": code})
    assert r2.json()["version"] == 2


def test_recipe_inline_streams_supported(client):
    r = client.post("/api/v1/gas/recipes", json={"name": "Inline mix", "streams": [
        {"gasComposition": {"methane": 1.0}, "share": 0.8},
        {"gasComposition": {"hydrogen": 1.0}, "share": 0.2},
    ]})
    assert r.status_code == 201, r.text
    run = client.post(f"/api/v1/gas/recipes/{r.json()['code']}/run")
    assert run.status_code == 200
    assert run.json()["composition"]["hydrogen"] > 0.15


def test_run_unknown_recipe_404(client):
    assert client.post("/api/v1/gas/recipes/nope/run").status_code == 404


def test_recipe_rejects_unknown_component(client):
    r = client.post("/api/v1/gas/recipes", json={"name": "bad", "streams": [
        {"gasComposition": {"kryptonite": 1.0}, "share": 1.0}]})
    assert r.status_code == 422
