from __future__ import annotations

import hmac
import logging
import mimetypes
import os
import secrets
import shutil
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .database import UPLOAD_DIR, get_connection, init_db
from .security import PASSWORD_COOKIE_MAX_AGE, SESSION_SECRET, VISITOR_COOKIE_MAX_AGE, VISITOR_COOKIE_NAME, hash_ip, hash_password, hash_visitor, make_slug, make_visitor_id, sign_password_cookie, verify_password, verify_password_cookie
from .services import clean_name, save_upload


app = FastAPI(title="HTML Drop", version="1.0.0")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET, max_age=60 * 60 * 24 * 14, same_site="lax", https_only=False, path="/")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"

logger = logging.getLogger(__name__)

BEIJING_TIME_MODIFIER = "+8 hours"
BEIJING_OFFSET = timedelta(hours=8)


@app.on_event("startup")
def startup() -> None:
    init_db()
    username = os.getenv("ADMIN_USERNAME", "admin")
    password = os.getenv("ADMIN_PASSWORD", "admin123")
    with get_connection() as db:
        existing = db.execute("SELECT id, password_hash FROM users WHERE username = ?", (username,)).fetchone()
        if existing is None:
            db.execute("INSERT INTO users(username, password_hash) VALUES (?, ?)", (username, hash_password(password)))
        elif not verify_password(password, existing["password_hash"]):
            # 环境变量是账号密码的事实来源：修改 ADMIN_PASSWORD 后重启即生效
            db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), existing["id"]))


def current_user(request: Request) -> sqlite3.Row:
    # 发布页与管理台同源，仅凭会话 cookie 无法区分"管理台"与"恶意发布页"。
    # 因此所有业务接口（含 /api/auth/me）必须携带与会话内令牌一致的 API 令牌。
    # 前端令牌保存在当前标签页的 sessionStorage 中，以支持刷新后恢复登录。
    header_token = request.headers.get("X-API-Token", "")
    if not header_token:
        authorization = request.headers.get("Authorization", "")
        if authorization.lower().startswith("bearer "):
            header_token = authorization[7:].strip()
    session_token = request.session.get("api_token", "")
    if not header_token or not session_token or not hmac.compare_digest(header_token, session_token):
        raise HTTPException(status_code=401, detail="请先登录")
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="请先登录")
    with get_connection() as db:
        user = db.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        request.session.clear()
        raise HTTPException(status_code=401, detail="登录已失效")
    return user


def serialize_link(row: sqlite3.Row, request: Request) -> dict:
    base_url = os.getenv("PUBLIC_BASE_URL", "").rstrip("/") or str(request.base_url).rstrip("/")
    return {
        "id": row["id"],
        "slug": row["slug"],
        "name": row["name"],
        "description": row["description"],
        "source_type": row["source_type"],
        "status": row["status"],
        "view_count": row["view_count"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "password_protected": bool(row["password_hash"]),
        "url": base_url + f"/p/{row['slug']}",
    }


@app.post("/api/auth/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)) -> dict:
    with get_connection() as db:
        user = db.execute("SELECT id, username, password_hash FROM users WHERE username = ?", (username.strip(),)).fetchone()
    if user is None or not verify_password(password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    # 先清空再写入：轮换会话，防止会话固定；同时签发 API 令牌（见 current_user）
    request.session.clear()
    token = secrets.token_urlsafe(32)
    request.session["user_id"] = user["id"]
    request.session["api_token"] = token
    return {"username": user["username"], "api_token": token, "default_password": verify_password("admin123", user["password_hash"])}


@app.post("/api/auth/logout")
def logout(request: Request) -> dict:
    request.session.clear()
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: sqlite3.Row = Depends(current_user)) -> dict:
    with get_connection() as db:
        password_hash = db.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()["password_hash"]
    return {"username": user["username"], "default_password": verify_password("admin123", password_hash)}


@app.post("/api/auth/password")
def change_password(user: sqlite3.Row = Depends(current_user), old_password: str = Form(...), new_password: str = Form(...)) -> dict:
    new_password = new_password.strip()
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 位")
    with get_connection() as db:
        row = db.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()
        if not verify_password(old_password, row["password_hash"]):
            raise HTTPException(status_code=400, detail="旧密码不正确")
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new_password), user["id"]))
    return {"ok": True}


@app.get("/api/links")
def list_links(request: Request, page: int = 1, page_size: int = 10, user: sqlite3.Row = Depends(current_user)) -> dict:
    page = max(1, page)
    page_size = min(max(1, page_size), 50)
    with get_connection() as db:
        total = db.execute("SELECT COUNT(*) AS c FROM links WHERE status != 'deleted'").fetchone()["c"]
        rows = db.execute("SELECT * FROM links WHERE status != 'deleted' ORDER BY created_at DESC LIMIT ? OFFSET ?", (page_size, (page - 1) * page_size)).fetchall()
    return {"items": [serialize_link(row, request) for row in rows], "total": total, "page": page, "page_size": page_size}


@app.get("/api/links/summary")
def links_summary(user: sqlite3.Row = Depends(current_user)) -> dict:
    with get_connection() as db:
        row = db.execute("SELECT COUNT(*) AS total, COALESCE(SUM(view_count), 0) AS total_views FROM links WHERE status != 'deleted'").fetchone()
        active = db.execute("SELECT COUNT(*) AS c FROM links WHERE status = 'active'").fetchone()["c"]
    return {"total": row["total"], "total_views": row["total_views"], "active": active}


@app.post("/api/links")
async def create_link(
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(""),
    description: str = Form(""),
    password: str = Form(""),
    user: sqlite3.Row = Depends(current_user),
) -> dict:
    slug = make_slug()
    source_type, storage_dir = await save_upload(file, slug)
    title = clean_name(name or Path(file.filename or "页面").stem)
    password_hash = hash_password(password) if password.strip() else None
    with get_connection() as db:
        db.execute("INSERT INTO links(slug, name, description, storage_dir, source_type, password_hash) VALUES (?, ?, ?, ?, ?, ?)", (slug, title, description.strip()[:500], storage_dir, source_type, password_hash))
        row = db.execute("SELECT * FROM links WHERE slug = ?", (slug,)).fetchone()
    return serialize_link(row, request)


@app.patch("/api/links/{link_id}")
def update_link(link_id: int, name: str = Form(...), description: str = Form(""), password: str = Form(""), clear_password: str = Form(""), user: sqlite3.Row = Depends(current_user)) -> dict:
    with get_connection() as db:
        if clear_password in {"1", "true", "on"}:
            # 显式移除密码保护
            db.execute("UPDATE links SET name = ?, description = ?, password_hash = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status != 'deleted'", (clean_name(name), description.strip()[:500], link_id))
        elif password.strip():
            # 填了新密码才更新；留空表示不修改现有密码
            db.execute("UPDATE links SET name = ?, description = ?, password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status != 'deleted'", (clean_name(name), description.strip()[:500], hash_password(password), link_id))
        else:
            db.execute("UPDATE links SET name = ?, description = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status != 'deleted'", (clean_name(name), description.strip()[:500], link_id))
        result = db.execute("SELECT changes() AS c").fetchone()["c"]
        if result == 0:
            raise HTTPException(status_code=404, detail="链接不存在")
        return {"ok": True}


@app.post("/api/links/{link_id}/upload")
async def replace_link(request: Request, link_id: int, file: UploadFile = File(...), user: sqlite3.Row = Depends(current_user)) -> dict:
    with get_connection() as db:
        row = db.execute("SELECT * FROM links WHERE id = ? AND status != 'deleted'", (link_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="链接不存在")
    source_type, storage_dir = await save_upload(file, row["slug"])
    with get_connection() as db:
        db.execute("UPDATE links SET source_type = ?, storage_dir = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (source_type, storage_dir, link_id))
        updated = db.execute("SELECT * FROM links WHERE id = ?", (link_id,)).fetchone()
    return serialize_link(updated, request)


@app.post("/api/links/{link_id}/{action}")
def set_link_state(link_id: int, action: str, user: sqlite3.Row = Depends(current_user)) -> dict:
    if action not in {"enable", "disable"}:
        raise HTTPException(status_code=404, detail="操作不存在")
    status = "active" if action == "enable" else "stopped"
    with get_connection() as db:
        result = db.execute("UPDATE links SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status != 'deleted'", (status, link_id))
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="链接不存在")
    return {"ok": True, "status": status}


@app.delete("/api/links/{link_id}")
def delete_link(link_id: int, user: sqlite3.Row = Depends(current_user)) -> dict:
    with get_connection() as db:
        row = db.execute("SELECT storage_dir FROM links WHERE id = ? AND status != 'deleted'", (link_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="链接不存在")
        db.execute("UPDATE links SET status = 'deleted', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (link_id,))
    storage = (UPLOAD_DIR / row["storage_dir"]).resolve()
    if UPLOAD_DIR.resolve() in storage.parents and storage.exists():
        shutil.rmtree(storage)
    return {"ok": True}


@app.get("/api/links/{link_id}/stats")
def link_stats(link_id: int, user: sqlite3.Row = Depends(current_user)) -> dict:
    with get_connection() as db:
        row = db.execute("SELECT id, view_count FROM links WHERE id = ? AND status != 'deleted'", (link_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="链接不存在")
        visitor_key = "COALESCE(visitor_hash, ip_hash)"
        beijing_day = f"date(datetime(visited_at, '{BEIJING_TIME_MODIFIER}'))"
        beijing_hour = f"strftime('%Y-%m-%d %H', visited_at, '{BEIJING_TIME_MODIFIER}')"
        daily = db.execute(f"SELECT {beijing_day} AS day, COUNT(*) AS pv, COUNT(DISTINCT {visitor_key}) AS uv FROM visits WHERE link_id = ? GROUP BY {beijing_day} ORDER BY {beijing_day} DESC LIMIT 90", (link_id,)).fetchall()
        hourly = db.execute(f"SELECT {beijing_hour} AS hour, COUNT(*) AS pv, COUNT(DISTINCT {visitor_key}) AS uv FROM visits WHERE link_id = ? AND visited_at >= datetime('now', '-24 hours') GROUP BY {beijing_hour} ORDER BY {beijing_hour} ASC", (link_id,)).fetchall()
        recent_uv = db.execute(f"SELECT COUNT(DISTINCT {visitor_key}) AS value FROM visits WHERE link_id = ? AND visited_at >= datetime('now', '-30 days')", (link_id,)).fetchone()["value"]
        total_uv = db.execute(f"SELECT COUNT(DISTINCT {visitor_key}) AS value FROM visits WHERE link_id = ?", (link_id,)).fetchone()["value"]
        peak = db.execute(f"SELECT {beijing_day} AS day, COUNT(*) AS pv FROM visits WHERE link_id = ? GROUP BY {beijing_day} ORDER BY pv DESC, {beijing_day} DESC LIMIT 1", (link_id,)).fetchone()
        browsers = db.execute("SELECT browser AS name, COUNT(*) AS value FROM visits WHERE link_id = ? GROUP BY browser ORDER BY value DESC LIMIT 8", (link_id,)).fetchall()
        devices = db.execute("SELECT device AS name, COUNT(*) AS value FROM visits WHERE link_id = ? GROUP BY device ORDER BY value DESC", (link_id,)).fetchall()
        oss = db.execute("SELECT os AS name, COUNT(*) AS value FROM visits WHERE link_id = ? GROUP BY os ORDER BY value DESC", (link_id,)).fetchall()
        referers = db.execute("SELECT CASE WHEN referer = '' THEN '(直接访问)' ELSE referer END AS name, COUNT(*) AS value FROM visits WHERE link_id = ? GROUP BY name ORDER BY value DESC LIMIT 8", (link_id,)).fetchall()
        recent = db.execute("SELECT visited_at, browser, os, device, referer FROM visits WHERE link_id = ? ORDER BY id DESC LIMIT 20", (link_id,)).fetchall()
    return {
        "view_count": row["view_count"], "uv": recent_uv, "total_uv": total_uv,
        "peak": dict(peak) if peak else None,
        "daily": [dict(item) for item in daily],
        "hourly": [dict(item) for item in hourly],
        "browsers": [dict(item) for item in browsers], "devices": [dict(item) for item in devices],
        "os": [dict(item) for item in oss], "referers": [dict(item) for item in referers],
        "recent": [dict(item) for item in recent],
    }


def _client_info(request: Request) -> tuple[str, str, str, str, str, str]:
    user_agent = request.headers.get("user-agent", "")
    lowered = user_agent.lower()
    # 顺序很关键：Edge UA 同时包含 "chrome"，必须先判 Edge 再判 Chrome；
    # iPad/iPod 的 UA 不含 "iphone"，设备与 OS 判断需一并覆盖。
    device = "mobile" if any(value in lowered for value in ("mobile", "android", "iphone", "ipad", "ipod")) else "desktop"
    browser = "Edge" if "edg/" in lowered else "Chrome" if "chrome" in lowered else "Safari" if "safari" in lowered else "Firefox" if "firefox" in lowered else "Other"
    operating_system = "Windows" if "windows" in lowered else "Android" if "android" in lowered else "iOS" if "iphone" in lowered or "ipad" in lowered or "ipod" in lowered else "macOS" if "mac os" in lowered else "Linux" if "linux" in lowered else "Other"
    return hash_ip(request.client.host if request.client else "unknown"), user_agent[:500], request.headers.get("referer", "")[:500], device, browser, operating_system


def _visitor_hash(request: Request) -> tuple[str, str | None]:
    visitor_id = request.cookies.get(VISITOR_COOKIE_NAME, "")
    if visitor_id and len(visitor_id) <= 128:
        return hash_visitor(visitor_id), None
    visitor_id = make_visitor_id()
    return hash_visitor(visitor_id), visitor_id


def _password_page(slug: str, error: str = "") -> HTMLResponse:
    error_html = f'<p class="error">{error}</p>' if error else ""
    html = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>访问密码 · HTML Drop</title>
<style>
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ min-height: 100vh; display: grid; place-items: center; padding: 24px; font-family: "PingFang SC","Microsoft YaHei",ui-rounded,sans-serif; background: linear-gradient(150deg,#fff3fb 0%,#f1efff 50%,#e9f7ff 100%); }}
  .card {{ position: relative; width: min(400px, 100%); padding: 44px 32px 30px; border-radius: 26px; background: #fff; box-shadow: 0 18px 50px rgba(120,110,190,.16); text-align: center; }}
  .face {{ font-size: 74px; line-height: 1; animation: peek 3.2s ease-in-out infinite; display: inline-block; }}
  @keyframes peek {{ 0%,100% {{ transform: translateY(0) rotate(-6deg); }} 50% {{ transform: translateY(-8px) rotate(6deg); }} }}
  .lock {{ position: absolute; top: 30px; right: 46px; font-size: 26px; animation: spin 6s linear infinite; }}
  @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
  h1 {{ margin-top: 18px; color: #7a5fb0; font-size: 25px; }}
  .sub {{ margin-top: 10px; color: #968ca8; font-size: 14px; line-height: 1.9; }}
  .error {{ margin-top: 14px; color: #c25b58; font-size: 13px; }}
  .dots {{ position: absolute; inset: 0; pointer-events: none; }}
  .dots i {{ position: absolute; border-radius: 50%; }}
  .dots i:nth-child(1) {{ top: 15%; left: 10%; width: 8px; height: 8px; background: #ffd7e8; }}
  .dots i:nth-child(2) {{ top: 22%; right: 12%; width: 12px; height: 12px; background: #cfe7ff; }}
  .dots i:nth-child(3) {{ bottom: 16%; left: 15%; width: 10px; height: 10px; background: #ffe9bd; }}
  .dots i:nth-child(4) {{ bottom: 12%; right: 18%; width: 7px; height: 7px; background: #d9f4e5; }}
  form {{ margin-top: 22px; }}
  input {{ width: 100%; padding: 13px 14px; border: 1.5px solid #dcd3f2; border-radius: 12px; outline: none; font-size: 15px; text-align: center; letter-spacing: .12em; transition: border-color .18s, box-shadow .18s; }}
  input:focus {{ border-color: #9f8fe0; box-shadow: 0 0 0 4px rgba(159,143,224,.15); }}
  button {{ width: 100%; margin-top: 13px; padding: 13px; border: 0; border-radius: 12px; color: #fff; background: #8b7bd6; font-size: 15px; font-weight: 700; cursor: pointer; transition: background .18s, transform .18s; }}
  button:hover {{ background: #7766c4; transform: translateY(-1px); }}
  .foot {{ margin-top: 26px; color: #c0b8d4; font-size: 11px; letter-spacing: .16em; }}
</style></head><body>
<div class="card">
  <div class="dots"><i></i><i></i><i></i><i></i></div>
  <div class="face">🤫</div>
  <div class="lock">🔒</div>
  <h1>嘘——这里藏着秘密～</h1>
  <p class="sub">主人给这个页面上了把小锁 🔒<br>输入正确的密码，才能溜进去偷偷看哦</p>
  {error_html}
  <form method="post" action="/p/{slug}/verify">
    <input type="password" name="password" placeholder="悄悄告诉我密码…" autofocus required>
    <button type="submit">进入页面 🔓</button>
  </form>
  <div class="foot">HTML DROP</div>
</div>
</body></html>"""
    return HTMLResponse(html, headers={"Cache-Control": "no-store"})


def _stopped_page() -> HTMLResponse:
    html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>页面休息中 · HTML Drop</title>
<style>
  * { box-sizing: border-box; margin: 0; }
  body { min-height: 100vh; display: grid; place-items: center; padding: 24px; font-family: "PingFang SC","Microsoft YaHei",ui-rounded,sans-serif; background: linear-gradient(150deg,#fff3f4 0%,#f1efff 50%,#e8f6ff 100%); }
  .card { position: relative; width: min(430px, 100%); padding: 46px 34px 30px; border-radius: 26px; background: #fff; box-shadow: 0 18px 50px rgba(120,110,190,.16); text-align: center; }
  .face { font-size: 76px; line-height: 1; animation: bob 3s ease-in-out infinite; }
  .zzz { position: absolute; top: 34px; right: 58px; height: 30px; width: 30px; font-size: 22px; color: #a69be0; font-weight: 800; }
  .zzz span { position: absolute; left: 0; top: 0; animation: floatz 2.6s ease-out infinite; opacity: 0; }
  .zzz span:nth-child(2) { animation-delay: .8s; }
  .zzz span:nth-child(3) { animation-delay: 1.6s; }
  @keyframes floatz { 0% { transform: translate(0,0); opacity: 0; } 25% { opacity: 1; } 100% { transform: translate(18px,-48px) scale(1.25); opacity: 0; } }
  @keyframes bob { 0%,100% { transform: translateY(0) rotate(-4deg); } 50% { transform: translateY(-9px) rotate(4deg); } }
  h1 { margin-top: 20px; color: #5b4f9e; font-size: 27px; }
  .sub { margin-top: 12px; color: #8d87a8; font-size: 14px; line-height: 1.9; }
  .pill { display: inline-block; margin-top: 24px; padding: 9px 18px; color: #7c6fd0; border: 1.5px dashed #c9c2f0; border-radius: 999px; background: #f7f5ff; font-size: 13px; }
  .dots { position: absolute; inset: 0; pointer-events: none; }
  .dots i { position: absolute; border-radius: 50%; }
  .dots i:nth-child(1) { top: 16%; left: 11%; width: 8px; height: 8px; background: #ffd7de; }
  .dots i:nth-child(2) { top: 24%; right: 13%; width: 12px; height: 12px; background: #cfe7ff; }
  .dots i:nth-child(3) { bottom: 18%; left: 16%; width: 10px; height: 10px; background: #ffe9bd; }
  .dots i:nth-child(4) { bottom: 14%; right: 19%; width: 7px; height: 7px; background: #d9f4e5; }
  .foot { margin-top: 28px; color: #b3acc9; font-size: 11px; letter-spacing: .16em; }
</style></head><body>
<div class="card">
  <div class="dots"><i></i><i></i><i></i><i></i></div>
  <div class="face">😴</div>
  <div class="zzz"><span>z</span><span>Z</span><span>z</span></div>
  <h1>这个页面睡着啦～</h1>
  <p class="sub">主人按下了暂停键，它正在被窝里呼呼大睡 😪<br>休息好了就会回来的，晚点再来看看叭</p>
  <div class="pill">🛌 页面休息站 · 随时欢迎回来</div>
  <div class="foot">HTML DROP</div>
</div>
</body></html>"""
    return HTMLResponse(html, status_code=404, headers={"Cache-Control": "no-store"})


def _not_found_page() -> HTMLResponse:
    html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>页面走丢了 · HTML Drop</title>
<style>
  * { box-sizing: border-box; margin: 0; }
  body { min-height: 100vh; display: grid; place-items: center; padding: 24px; font-family: "PingFang SC","Microsoft YaHei",ui-rounded,sans-serif; background: linear-gradient(150deg,#fff8f0 0%,#f2f7ff 55%,#f0fff8 100%); }
  .card { position: relative; width: min(430px, 100%); padding: 46px 34px 30px; border-radius: 26px; background: #fff; box-shadow: 0 18px 50px rgba(120,110,190,.16); text-align: center; }
  .face { font-size: 76px; line-height: 1; animation: wiggle 2.8s ease-in-out infinite; }
  @keyframes wiggle { 0%,100% { transform: rotate(0); } 25% { transform: rotate(-12deg); } 75% { transform: rotate(12deg); } }
  .spark { position: absolute; top: 36px; left: 64px; font-size: 20px; animation: spin 5s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  h1 { margin-top: 20px; color: #8a6d3a; font-size: 27px; }
  .sub { margin-top: 12px; color: #9a8f78; font-size: 14px; line-height: 1.9; }
  .pill { display: inline-block; margin-top: 24px; padding: 9px 18px; color: #c08a3e; border: 1.5px dashed #ecd9b4; border-radius: 999px; background: #fffaf0; font-size: 13px; }
  .paw { position: absolute; right: 58px; bottom: 96px; font-size: 26px; animation: bob2 2.4s ease-in-out infinite; }
  @keyframes bob2 { 0%,100% { transform: translateY(0) rotate(8deg); } 50% { transform: translateY(-7px) rotate(-8deg); } }
  .foot { margin-top: 28px; color: #c3b9a4; font-size: 11px; letter-spacing: .16em; }
</style></head><body>
<div class="card">
  <div class="face">🕵️</div>
  <div class="spark">✨</div>
  <h1>咦，页面走丢了～</h1>
  <p class="sub">侦探翻遍了口袋也没找到它 🧐<br>它可能从未出生，或者已经被主人带走了</p>
  <div class="pill">🐾 404 · 线索不足，请回管理台看看</div>
  <div class="paw">🐾</div>
  <div class="foot">HTML DROP</div>
</div>
</body></html>"""
    return HTMLResponse(html, status_code=404, headers={"Cache-Control": "no-store"})


def _serve_page(request: Request, slug: str, asset_path: str = ""):
    new_visitor_id: str | None = None
    with get_connection() as db:
        link = db.execute("SELECT * FROM links WHERE slug = ? AND status != 'deleted'", (slug,)).fetchone()
        if link is None:
            return _not_found_page()
        if link["status"] != "active":
            return _stopped_page()
        if link["password_hash"]:
            cookie_value = request.cookies.get(f"pwd_{slug}", "")
            if not verify_password_cookie(slug, link["password_hash"], cookie_value):
                return _password_page(slug)
        root = (UPLOAD_DIR / link["storage_dir"]).resolve()
        requested = (root / (asset_path or "index.html")).resolve()
        if root not in requested.parents and requested != root:
            raise HTTPException(status_code=404, detail="资源不存在")
        if not requested.is_file():
            raise HTTPException(status_code=404, detail="资源不存在")
        if not asset_path or asset_path.lower() == "index.html":
            try:
                ip_hash, user_agent, referer, device, browser, operating_system = _client_info(request)
                visitor_hash, new_visitor_id = _visitor_hash(request)
                db.execute("UPDATE links SET view_count = view_count + 1 WHERE id = ?", (link["id"],))
                day = (datetime.now(UTC) + BEIJING_OFFSET).date().isoformat()
                db.execute("INSERT INTO visits(link_id, day, ip_hash, visitor_hash, user_agent, referer, device, browser, os) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (link["id"], day, ip_hash, visitor_hash, user_agent, referer, device, browser, operating_system))
            except Exception:
                # 统计失败不应影响页面访问，只记录日志
                logger.exception("记录访问统计失败 (slug=%s)", slug)
    media_type = mimetypes.guess_type(str(requested))[0] or "application/octet-stream"
    response = FileResponse(requested, media_type=media_type)
    if new_visitor_id is not None:
        response.set_cookie(key=VISITOR_COOKIE_NAME, value=new_visitor_id, max_age=VISITOR_COOKIE_MAX_AGE, path="/p/", httponly=True, samesite="lax", secure=request.url.scheme == "https")
    return response


@app.post("/p/{slug}/verify")
def verify_page_password(request: Request, slug: str, password: str = Form(...)) -> Response:
    with get_connection() as db:
        link = db.execute("SELECT * FROM links WHERE slug = ? AND status != 'deleted'", (slug,)).fetchone()
    if link is None:
        return _not_found_page()
    if link["status"] != "active":
        return _stopped_page()
    if not link["password_hash"]:
        raise HTTPException(status_code=404, detail="页面不存在")
    if not verify_password(password, link["password_hash"]):
        return _password_page(slug, error="密码不对哦，再想想？🤔")
    response = RedirectResponse(url=f"/p/{slug}", status_code=303)
    response.set_cookie(key=f"pwd_{slug}", value=sign_password_cookie(slug, link["password_hash"]), max_age=PASSWORD_COOKIE_MAX_AGE, path="/p/", httponly=True, samesite="lax")
    return response


@app.get("/p/{slug}")
def public_index(request: Request, slug: str):
    return _serve_page(request, slug)


@app.get("/p/{slug}/{asset_path:path}")
def public_asset(request: Request, slug: str, asset_path: str):
    return _serve_page(request, slug, asset_path)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/{path:path}")
def frontend(path: str):
    if path == "api" or path.startswith("api/") or path == "p" or path.startswith("p/"):
        raise HTTPException(status_code=404, detail="资源不存在")
    if not FRONTEND_DIST.exists():
        return JSONResponse({"message": "前端尚未构建，请运行 npm run build"}, status_code=404)
    requested = (FRONTEND_DIST / path).resolve()
    if FRONTEND_DIST.resolve() in requested.parents and requested.is_file():
        return FileResponse(requested)
    return FileResponse(FRONTEND_DIST / "index.html")
