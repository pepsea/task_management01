import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS ideas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    area TEXT NOT NULL,
    related TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    start_at TEXT NOT NULL,
    due_at TEXT NOT NULL,
    priority TEXT NOT NULL CHECK (priority IN ('high', 'mid', 'low')),
    done INTEGER NOT NULL DEFAULT 0,
    idea_id INTEGER REFERENCES ideas(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS brainstorm (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    date TEXT NOT NULL,
    time TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def db_path() -> Path:
    return Path(os.environ.get("APP_DB_PATH", DEFAULT_DB_PATH))


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # FastAPI は同期の依存関数とハンドラーを別スレッドで動かすことがあるため
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with closing(connect()) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def get_conn():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def now_iso() -> str:
    return datetime.now().isoformat()
