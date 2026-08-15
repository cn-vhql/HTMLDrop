"""Stats endpoint tests."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import app.database as database
from conftest import make_upload


def _visit(client, slug, ua, ref=""):
    headers = {"user-agent": ua}
    if ref:
        headers["referer"] = ref
    client.get(f"/p/{slug}", headers=headers)


def test_empty_stats(client, auth):
    r = client.post("/api/links", data={"name": "空"}, files=make_upload(), headers=auth)
    link = r.json()
    s = client.get(f"/api/links/{link['id']}/stats", headers=auth).json()
    assert s["view_count"] == 0
    assert s["uv"] == 0
    assert s["total_uv"] == 0
    assert s["peak"] is None
    assert s["daily"] == []
    assert s["hourly"] == []
    assert s["recent"] == []
    assert s["browsers"] == [] and s["devices"] == [] and s["os"] == [] and s["referers"] == []


def test_stats_after_visits(client, auth):
    r = client.post("/api/links", data={"name": "统计"}, files=make_upload(content=b"<h1>s</h1>"), headers=auth)
    link = r.json()
    slug = link["slug"]
    uas = [
        ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36", "https://a.com/ref"),
        ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1", ""),
    ]
    for ua, ref in uas * 2:
        _visit(client, slug, ua, ref)

    s = client.get(f"/api/links/{link['id']}/stats", headers=auth).json()
    assert s["view_count"] == 4
    # TestClient 所有请求来自同一 client IP -> UV 为 1
    assert s["uv"] == 1
    assert s["total_uv"] == 1
    assert s["peak"] is not None and s["peak"]["pv"] == 4
    assert len(s["daily"]) == 1 and s["daily"][0]["pv"] == 4 and s["daily"][0]["uv"] == 1
    assert len(s["hourly"]) >= 1
    assert {b["name"] for b in s["browsers"]} == {"Chrome", "Safari"}
    assert {d["name"] for d in s["devices"]} == {"desktop", "mobile"}
    assert {o["name"] for o in s["os"]} == {"Windows", "iOS"}
    assert {ref["name"] for ref in s["referers"]} == {"https://a.com/ref", "(直接访问)"}
    assert len(s["recent"]) == 4


def test_stats_uv_with_distinct_ips(client, auth):
    r = client.post("/api/links", data={"name": "多IP"}, files=make_upload(content=b"<h1>m</h1>"), headers=auth)
    link = r.json()
    slug = link["slug"]
    _visit(client, slug, "Mozilla/5.0 (Windows NT 10.0) Chrome/120.0")
    today = datetime.now(UTC).date().isoformat()
    with database.get_connection() as db:
        db.execute("INSERT INTO visits(link_id, day, ip_hash, user_agent, referer, device, browser, os) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (link["id"], today, "hash-extra-ip", "UA", "", "desktop", "Chrome", "Windows"))
    s = client.get(f"/api/links/{link['id']}/stats", headers=auth).json()
    assert s["total_uv"] == 2
    assert s["uv"] == 2
    assert s["daily"][0]["uv"] == 2


def test_stats_hourly_window(client, auth):
    r = client.post("/api/links", data={"name": "小时"}, files=make_upload(content=b"<h1>h</h1>"), headers=auth)
    link = r.json()
    now = datetime.now(UTC)
    with database.get_connection() as db:
        for hours_ago, ip in [(1, "h1"), (2, "h2"), (30, "h3"), (50, "h4")]:
            when = now - timedelta(hours=hours_ago)
            db.execute(
                "INSERT INTO visits(link_id, day, visited_at, ip_hash, user_agent, referer, device, browser, os) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (link["id"], when.date().isoformat(), when.strftime("%Y-%m-%d %H:%M:%S"), ip, "UA", "", "desktop", "Chrome", "Windows"),
            )
    s = client.get(f"/api/links/{link['id']}/stats", headers=auth).json()
    assert sum(h["pv"] for h in s["hourly"]) == 2  # 仅 1、2 小时前在 24h 窗口内
    assert len(s["daily"]) >= 2  # 至少今天与 30 小时前的日子（跨日边界时更多）
    assert sum(d["pv"] for d in s["daily"]) == 4


def test_stats_requires_auth(client, auth):
    r = client.post("/api/links", data={"name": "x"}, files=make_upload(), headers=auth)
    link = r.json()
    assert client.get(f"/api/links/{link['id']}/stats").status_code == 401
    assert client.get("/api/links/99999/stats", headers=auth).status_code == 404
