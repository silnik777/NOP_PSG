"""The web GUI is served as static assets and the root redirects to it."""

from __future__ import annotations


def test_root_redirects_to_app(client):
    r = client.get("/", follow_redirects=False)
    assert r.status_code in (307, 308)
    assert r.headers["location"] == "/app/"


def test_app_index_served(client):
    r = client.get("/app/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "app.js" in r.text
    assert "e-GSD" in r.text


def test_app_static_assets_served(client):
    js = client.get("/app/app.js")
    assert js.status_code == 200
    assert "/api/v1" in js.text  # GUI talks to the API
    css = client.get("/app/styles.css")
    assert css.status_code == 200
