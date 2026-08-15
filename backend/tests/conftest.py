"""Pytest fixtures: isolate DB/upload dirs and provide authenticated client."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.database as database  # noqa: E402
import app.main as main  # noqa: E402
import app.services as services  # noqa: E402


def make_upload(name: str = "page.html", content: bytes = b"<h1>hello</h1>"):
    return {"file": (name, content, "text/html")}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """TestClient 使用隔离的临时数据/上传目录。"""
    monkeypatch.setattr(database, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(database, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "data" / "app.db")
    monkeypatch.setattr(main, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(services, "UPLOAD_DIR", tmp_path / "uploads")
    with TestClient(main.app, follow_redirects=False) as test_client:
        yield test_client


@pytest.fixture()
def login(client) -> dict:
    response = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture()
def token(login) -> str:
    return login["api_token"]


@pytest.fixture()
def auth(token) -> dict:
    return {"X-API-Token": token}


@pytest.fixture()
def create_link(client, auth):
    """返回创建链接的辅助函数，带默认 HTML 文件。"""

    def _create(name: str = "测试页", **overrides):
        files = overrides.pop("files", None) or make_upload()
        data = {"name": name, **overrides}
        response = client.post("/api/links", data=data, files=files, headers=auth)
        assert response.status_code == 200, response.text
        return response.json()

    return _create
