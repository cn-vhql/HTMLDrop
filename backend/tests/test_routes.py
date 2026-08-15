"""Misc routes: health, frontend hosting, API catch-all."""
from __future__ import annotations


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_frontend_dist_served(client):
    # 若 frontend/dist 存在则返回页面，否则返回 404 JSON 提示
    r = client.get("/")
    assert r.status_code in (200, 404)
    if r.status_code == 404:
        assert "前端尚未构建" in r.text


def test_frontend_dist_served_index_fallback(client, monkeypatch):
    import app.main as main

    missing = main.FRONTEND_DIST.parent / "__no_dist__"
    monkeypatch.setattr(main, "FRONTEND_DIST", missing)
    r = client.get("/")
    assert r.status_code == 404
    assert "前端尚未构建" in r.json()["message"]


def test_api_catch_all_not_served_as_frontend(client):
    r = client.get("/api/this/does/not/exist")
    assert r.status_code == 404
    assert "资源不存在" in r.json()["detail"]


def test_p_catch_all_not_served_as_frontend(client):
    r = client.get("/p/anything/here")
    # 应返回后端 404（可爱页/JSON），而不是前端 SPA 兜底 HTML
    assert r.status_code == 404
    assert "资源不存在" not in r.text


def test_static_asset_from_dist(client):
    import app.main as main

    if not main.FRONTEND_DIST.exists():
        import pytest
        pytest.skip("frontend dist 未构建")
    r = client.get("/vite.svg")  # 不存在的静态资源 -> SPA fallback index.html
    assert r.status_code in (200, 404)
