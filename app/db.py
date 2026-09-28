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
    memo TEXT NOT NULL DEFAULT '',
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
CREATE TABLE IF NOT EXISTS areas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS related_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    area_id INTEGER NOT NULL REFERENCES areas(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    UNIQUE (area_id, name)
);
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    color TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS idea_tags (
    idea_id INTEGER NOT NULL REFERENCES ideas(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    PRIMARY KEY (idea_id, tag_id)
);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    # 列を後から追加したテーブルは、既存の DB に ALTER TABLE で追加する
    task_columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
    if "memo" not in task_columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN memo TEXT NOT NULL DEFAULT ''")
    # 登録制にする前に作られたタスクの領域・関連項目をマスタに取り込む
    conn.execute(
        "INSERT OR IGNORE INTO areas (name) SELECT area FROM tasks GROUP BY area ORDER BY MIN(id)"
    )
    conn.execute(
        """INSERT OR IGNORE INTO related_items (area_id, name)
           SELECT a.id, t.related FROM tasks t JOIN areas a ON a.name = t.area
           WHERE t.related != '' GROUP BY a.id, t.related ORDER BY MIN(t.id)"""
    )


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
        _migrate(conn)
        conn.commit()


def get_conn():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def now_iso() -> str:
    return datetime.now().isoformat()
