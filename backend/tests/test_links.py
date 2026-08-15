"""Link CRUD, pagination, summary tests."""
from __future__ import annotations

from conftest import make_upload


def test_create_html_link(client, auth):
    r = client.post("/api/links", data={"name": "首页"}, files=make_upload(), headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "首页"
    assert body["source_type"] == "html"
    assert body["status"] == "active"
    assert body["view_count"] == 0
    assert body["password_protected"] is False
    assert body["slug"] and body["url"].endswith(f"/p/{body['slug']}")


def test_create_with_description_and_password(client, auth):
    r = client.post("/api/links", data={"name": "加密", "description": "备注内容", "password": "p@ss"}, files=make_upload(), headers=auth)
    body = r.json()
    assert body["description"] == "备注内容"
    assert body["password_protected"] is True


def test_create_rejects_bad_extension(client, auth):
    r = client.post("/api/links", data={"name": "坏文件"}, files={"file": ("evil.exe", b"MZ", "application/octet-stream")}, headers=auth)
    assert r.status_code == 400


def test_create_requires_auth(client):
    r = client.post("/api/links", data={"name": "x"}, files=make_upload())
    assert r.status_code == 401


def test_list_pagination(client, auth, create_link):
    for i in range(5):
        create_link(f"页面{i}")
    r = client.get("/api/links?page=1&page_size=3", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 3
    assert body["total"] == 5
    assert body["page"] == 1
    assert body["page_size"] == 3
    # 同名秒创建时排序不稳定，只验证内容与数量
    names = {item["name"] for item in body["items"]}
    assert names <= {"页面0", "页面1", "页面2", "页面3", "页面4"}

    r = client.get("/api/links?page=2&page_size=3", headers=auth)
    assert len(r.json()["items"]) == 2

    # 越界页返回空列表
    r = client.get("/api/links?page=99&page_size=3", headers=auth)
    assert r.json()["items"] == []

    # page_size 上限 50
    r = client.get("/api/links?page=1&page_size=999", headers=auth)
    assert len(r.json()["items"]) == 5


def test_summary(client, auth, create_link):
    assert client.get("/api/links/summary", headers=auth).json() == {"total": 0, "total_views": 0, "active": 0}
    create_link("一")
    create_link("二")
    s = client.get("/api/links/summary", headers=auth).json()
    assert s["total"] == 2
    assert s["active"] == 2


def test_update_link(client, auth, create_link):
    link = create_link("原名")
    r = client.patch(f"/api/links/{link['id']}", data={"name": "新名", "description": "新备注"}, headers=auth)
    assert r.status_code == 200
    items = client.get("/api/links", headers=auth).json()["items"]
    updated = next(item for item in items if item["id"] == link["id"])
    assert updated["name"] == "新名"
    assert updated["description"] == "新备注"


def test_update_404_for_unknown(client, auth):
    r = client.patch("/api/links/99999", data={"name": "x"}, headers=auth)
    assert r.status_code == 404


def test_update_password_only_when_provided(client, auth, create_link):
    link = create_link("无密码")
    # 留空不修改
    client.patch(f"/api/links/{link['id']}", data={"name": "无密码"}, headers=auth)
    items = client.get("/api/links", headers=auth).json()["items"]
    assert next(i for i in items if i["id"] == link["id"])["password_protected"] is False
    # 填密码则启用
    client.patch(f"/api/links/{link['id']}", data={"name": "无密码", "password": "abc"}, headers=auth)
    items = client.get("/api/links", headers=auth).json()["items"]
    assert next(i for i in items if i["id"] == link["id"])["password_protected"] is True
    # clear_password 显式移除
    client.patch(f"/api/links/{link['id']}", data={"name": "无密码", "clear_password": "1"}, headers=auth)
    items = client.get("/api/links", headers=auth).json()["items"]
    assert next(i for i in items if i["id"] == link["id"])["password_protected"] is False


def test_enable_disable(client, auth, create_link):
    link = create_link("状态页")
    r = client.post(f"/api/links/{link['id']}/disable", headers=auth)
    assert r.json()["status"] == "stopped"
    r = client.post(f"/api/links/{link['id']}/enable", headers=auth)
    assert r.json()["status"] == "active"
    # 非法 action
    r = client.post(f"/api/links/{link['id']}/explode", headers=auth)
    assert r.status_code == 404


def test_delete_removes_files(client, auth, create_link, monkeypatch):
    import app.services as services

    uploads = services.UPLOAD_DIR
    link = create_link("待删")
    storage = uploads / link["slug"]
    assert storage.is_dir()
    r = client.delete(f"/api/links/{link['id']}", headers=auth)
    assert r.status_code == 200
    assert not storage.exists()
    assert client.get("/api/links", headers=auth).json()["total"] == 0


def test_replace_file(client, auth, create_link):
    link = create_link("替换")
    r = client.post(f"/api/links/{link['id']}/upload", files={"file": ("new.html", b"<h1>new content</h1>", "text/html")}, headers=auth)
    assert r.status_code == 200
    page = client.get(f"/p/{link['slug']}")
    assert "<h1>new content</h1>" in page.text
