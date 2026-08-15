"""Public page serving, password protection, cute pages, visit counting."""
from __future__ import annotations

from conftest import make_upload


def test_public_page_served_and_counts_view(client, auth):
    r = client.post("/api/links", data={"name": "公开"}, files=make_upload(content=b"<h1>visible</h1>"), headers=auth)
    slug = r.json()["slug"]
    page = client.get(f"/p/{slug}")
    assert page.status_code == 200
    assert "<h1>visible</h1>" in page.text
    # view_count 与 visits 记录
    items = client.get("/api/links", headers=auth).json()["items"]
    assert next(i for i in items if i["slug"] == slug)["view_count"] == 1


def test_index_html_explicit_counting(client, auth):
    r = client.post("/api/links", data={"name": "x"}, files=make_upload(), headers=auth)
    slug = r.json()["slug"]
    client.get(f"/p/{slug}/index.html")
    items = client.get("/api/links", headers=auth).json()["items"]
    assert next(i for i in items if i["slug"] == slug)["view_count"] == 1


def test_asset_request_does_not_count(client, auth):
    r = client.post("/api/links", data={"name": "x"}, files=make_upload(), headers=auth)
    slug = r.json()["slug"]
    client.get(f"/p/{slug}/missing.js")
    items = client.get("/api/links", headers=auth).json()["items"]
    assert next(i for i in items if i["slug"] == slug)["view_count"] == 0


def test_stopped_page_shows_cute_page(client, auth):
    r = client.post("/api/links", data={"name": "停"}, files=make_upload(), headers=auth)
    link = r.json()
    client.post(f"/api/links/{link['id']}/disable", headers=auth)
    page = client.get(f"/p/{link['slug']}")
    assert page.status_code == 404
    assert "这个页面睡着啦" in page.text


def test_unknown_slug_shows_not_found_page(client):
    page = client.get("/p/does-not-exist")
    assert page.status_code == 404
    assert "页面走丢了" in page.text


def test_missing_asset_404(client, auth):
    r = client.post("/api/links", data={"name": "x"}, files=make_upload(), headers=auth)
    slug = r.json()["slug"]
    assert client.get(f"/p/{slug}/no-such-file.png").status_code == 404


def test_path_traversal_blocked(client, auth):
    # httpx/TestClient 会规范化 URL 路径，因此直接调用 _serve_page 验证后端防护
    from starlette.requests import Request

    import app.main as main

    r = client.post("/api/links", data={"name": "x"}, files=make_upload(), headers=auth)
    slug = r.json()["slug"]
    scope = {
        "type": "http", "method": "GET", "path": f"/p/{slug}/../../app/main.py",
        "headers": [(b"host", b"test"), (b"user-agent", b"UA")], "query_string": b"",
        "scheme": "http", "server": ("test", 80), "client": ("1.2.3.4", 1), "http_version": "1.1",
    }
    request = Request(scope)
    try:
        main._serve_page(request, slug, "../../app/main.py")
        raise AssertionError("应拒绝路径穿越")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 404


class TestPasswordProtection:
    def _make_protected(self, client, auth, password="secret"):
        r = client.post("/api/links", data={"name": "加密", "password": password}, files=make_upload(content=b"<h1>locked content</h1>"), headers=auth)
        assert r.status_code == 200
        return r.json()

    def test_no_cookie_shows_password_page(self, client, auth):
        link = self._make_protected(client, auth)
        page = client.get(f"/p/{link['slug']}")
        assert page.status_code == 200
        assert "这里藏着秘密" in page.text
        assert "locked content" not in page.text

    def test_wrong_password(self, client, auth):
        link = self._make_protected(client, auth)
        r = client.post(f"/p/{link['slug']}/verify", data={"password": "wrong"})
        assert "密码不对哦" in r.text

    def test_correct_password_sets_cookie_and_serves(self, client, auth):
        link = self._make_protected(client, auth)
        r = client.post(f"/p/{link['slug']}/verify", data={"password": "secret"})
        assert r.status_code == 303
        assert any(k.startswith("pwd_") for k in client.cookies.keys())
        page = client.get(f"/p/{link['slug']}")
        assert "<h1>locked content</h1>" in page.text

    def test_assets_accessible_with_cookie(self, client, auth):
        link = self._make_protected(client, auth)
        client.post(f"/p/{link['slug']}/verify", data={"password": "secret"})
        assert client.get(f"/p/{link['slug']}/index.html").status_code == 200

    def test_password_change_invalidates_cookie(self, client, auth):
        link = self._make_protected(client, auth)
        client.post(f"/p/{link['slug']}/verify", data={"password": "secret"})
        client.patch(f"/api/links/{link['id']}", data={"name": "加密", "password": "newpass"}, headers=auth)
        page = client.get(f"/p/{link['slug']}")
        assert "这里藏着秘密" in page.text
        r = client.post(f"/p/{link['slug']}/verify", data={"password": "newpass"})
        assert r.status_code == 303

    def test_clear_password_removes_restriction(self, client, auth):
        link = self._make_protected(client, auth)
        # 移除密码后可直接访问
        r = client.patch(f"/api/links/{link['id']}", data={"name": "加密", "clear_password": "1"}, headers=auth)
        assert r.status_code == 200
        items = client.get("/api/links", headers=auth).json()["items"]
        assert next(i for i in items if i["id"] == link["id"])["password_protected"] is False
        page = client.get(f"/p/{link['slug']}")
        assert "<h1>locked content</h1>" in page.text

    def test_verify_404_for_unprotected(self, client, auth):
        r = client.post("/api/links", data={"name": "公开"}, files=make_upload(), headers=auth)
        slug = r.json()["slug"]
        assert client.post(f"/p/{slug}/verify", data={"password": "x"}).status_code == 404


class TestClientInfo:
    def test_edge_detected_before_chrome(self):
        from app.main import _client_info
        from starlette.requests import Request

        scope = {"type": "http", "method": "GET", "path": "/p/x", "headers": [(b"user-agent", b"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36 Edg/120.0")], "query_string": b"", "scheme": "http", "server": ("t", 80), "client": ("1.2.3.4", 1), "http_version": "1.1"}
        device, browser, os_name = _client_info(Request(scope))[3:]
        assert browser == "Edge"
        assert os_name == "Windows"

    def test_ipad_is_mobile_ios(self):
        from app.main import _client_info
        from starlette.requests import Request

        scope = {"type": "http", "method": "GET", "path": "/p/x", "headers": [(b"user-agent", b"Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")], "query_string": b"", "scheme": "http", "server": ("t", 80), "client": ("1.2.3.4", 1), "http_version": "1.1"}
        device, browser, os_name = _client_info(Request(scope))[3:]
        assert device == "mobile"
        assert os_name == "iOS"
