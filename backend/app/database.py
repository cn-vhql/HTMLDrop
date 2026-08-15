from __future__ import annotations

import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = BASE_DIR / "uploads"
DB_PATH = DATA_DIR / "app.db"


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    with get_connection() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                storage_dir TEXT NOT NULL,
                source_type TEXT NOT NULL CHECK (source_type IN ('html', 'zip')),
                status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'stopped', 'deleted')),
                view_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link_id INTEGER NOT NULL REFERENCES links(id) ON DELETE CASCADE,
                visited_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                day TEXT NOT NULL,
                ip_hash TEXT NOT NULL,
                user_agent TEXT NOT NULL DEFAULT '',
                referer TEXT NOT NULL DEFAULT '',
                device TEXT NOT NULL DEFAULT 'desktop',
                browser TEXT NOT NULL DEFAULT 'Other',
                os TEXT NOT NULL DEFAULT 'Other'
            );

            CREATE INDEX IF NOT EXISTS idx_visits_link_day ON visits(link_id, day);
            CREATE INDEX IF NOT EXISTS idx_visits_link_ip ON visits(link_id, ip_hash);
            """
        )
        # 兼容旧库：为 links 表补充访问密码列（SQLite 无 ADD COLUMN IF NOT EXISTS）
        columns = {row["name"] for row in db.execute("PRAGMA table_info(links)")}
        if "password_hash" not in columns:
            db.execute("ALTER TABLE links ADD COLUMN password_hash TEXT")

