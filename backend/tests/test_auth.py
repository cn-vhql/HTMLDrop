"""Auth & API-token tests."""
from __future__ import annotations


def test_login_success_returns_token_and_default_password(client):
    r = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "admin"
    assert len(body["api_token"]) >= 32
    assert body["default_password"] is True


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", data={"username": "admin", "password": "nope"})
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post("/api/auth/login", data={"username": "ghost", "password": "admin123"})
    assert r.status_code == 401


def test_me_requires_token_even_with_session_cookie(client, token):
    # 有会话 cookie 但无 X-API-Token -> 401（同源隔离的关键属性）
    r = client.get("/api/auth/me")
    assert r.status_code == 401
    r = client.get("/api/auth/me", headers={"X-API-Token": token})
    assert r.status_code == 200
    assert r.json()["username"] == "admin"


def test_me_wrong_token(client):
    r = client.get("/api/auth/me", headers={"X-API-Token": "forged-token"})
    assert r.status_code == 401


def test_me_returns_default_password_flag(client, token):
    r = client.get("/api/auth/me", headers={"X-API-Token": token})
    assert r.json()["default_password"] is True


def test_business_api_requires_token(client):
    r = client.get("/api/links")
    assert r.status_code == 401


def test_logout_invalidates_token(client, token):
    r = client.post("/api/auth/logout")
    assert r.status_code == 200
    r = client.get("/api/auth/me", headers={"X-API-Token": token})
    assert r.status_code == 401


def test_session_rotated_on_login(client, token):
    # 再次登录后旧令牌失效（会话轮换）
    r = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    r = client.get("/api/auth/me", headers={"X-API-Token": token})
    assert r.status_code == 401


def test_change_password_success(client, token):
    auth = {"X-API-Token": token}
    r = client.post("/api/auth/password", data={"old_password": "admin123", "new_password": "newpass123"}, headers=auth)
    assert r.status_code == 200
    # 默认密码标记变为 false
    assert client.get("/api/auth/me", headers=auth).json()["default_password"] is False
    # 旧密码失效、新密码可登录
    assert client.post("/api/auth/login", data={"username": "admin", "password": "admin123"}).status_code == 401
    assert client.post("/api/auth/login", data={"username": "admin", "password": "newpass123"}).status_code == 200


def test_change_password_wrong_old(client, token):
    r = client.post("/api/auth/password", data={"old_password": "wrong", "new_password": "newpass123"}, headers={"X-API-Token": token})
    assert r.status_code == 400


def test_change_password_too_short(client, token):
    r = client.post("/api/auth/password", data={"old_password": "admin123", "new_password": "123"}, headers={"X-API-Token": token})
    assert r.status_code == 400


def test_change_password_requires_auth(client):
    r = client.post("/api/auth/password", data={"old_password": "x", "new_password": "newpass123"})
    assert r.status_code == 401
