import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from app.colors import next_color

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS ideas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    archived_at TEXT,
    prioritized INTEGER NOT NULL DEFAULT 0,
    position INTEGER NOT NULL DEFAULT 0,
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
    today_on TEXT,
    links TEXT NOT NULL DEFAULT '[]',
    done_at TEXT,
    recurring_id INTEGER REFERENCES recurring_tasks(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
-- 定期タスク（繰り返しのひな形）。回ごとに普通のタスクを作る
--   rule: monthly_day（毎月 day 日）/ monthly_weekday（毎月 第 nth weekday 曜日、nth=5 は最終）/ weekly（毎週 weekday 曜日）
--   weekday は 0=月 … 6=日。繰り返しの日を期限にし、lead_days 日前を開始にする
--   generated_until: この日までの回は作成済み（NULL ならまだ作っていない）
CREATE TABLE IF NOT EXISTS recurring_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    area TEXT NOT NULL,
    related TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    priority TEXT NOT NULL CHECK (priority IN ('high', 'mid', 'low')),
    memo TEXT NOT NULL DEFAULT '',
    rule TEXT NOT NULL CHECK (rule IN ('monthly_day', 'monthly_weekday', 'weekly')),
    day INTEGER,
    nth INTEGER,
    weekday INTEGER,
    lead_days INTEGER NOT NULL DEFAULT 0,
    start_from TEXT NOT NULL,
    generated_until TEXT,
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
    name TEXT NOT NULL UNIQUE,
    color TEXT
);
CREATE TABLE IF NOT EXISTS related_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    pinned INTEGER NOT NULL DEFAULT 0,
    position INTEGER NOT NULL DEFAULT 0,
    archived_at TEXT,
    note_date TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quick_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT '',
    target TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    renewed_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
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
CREATE TABLE IF NOT EXISTS note_tags (
    note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    PRIMARY KEY (note_id, tag_id)
);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    # 列を後から追加したテーブルは、既存の DB に ALTER TABLE で追加する
    task_columns = {row[1] for row in conn.execute("PRAGMA table_info(tasks)")}
    if "memo" not in task_columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN memo TEXT NOT NULL DEFAULT ''")
    if "today_on" not in task_columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN today_on TEXT")
    if "links" not in task_columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN links TEXT NOT NULL DEFAULT '[]'")
    if "done_at" not in task_columns:
        # 完了した日時。導入前に完了していたタスクは最後に更新した日時を完了日時とみなす
        conn.execute("ALTER TABLE tasks ADD COLUMN done_at TEXT")
        conn.execute("UPDATE tasks SET done_at = updated_at WHERE done = 1")
    if "recurring_id" not in task_columns:
        conn.execute("ALTER TABLE tasks ADD COLUMN recurring_id INTEGER REFERENCES recurring_tasks(id) ON DELETE SET NULL")
    idea_columns = {row[1] for row in conn.execute("PRAGMA table_info(ideas)")}
    if "archived_at" not in idea_columns:
        conn.execute("ALTER TABLE ideas ADD COLUMN archived_at TEXT")
    if "prioritized" not in idea_columns:
        conn.execute("ALTER TABLE ideas ADD COLUMN prioritized INTEGER NOT NULL DEFAULT 0")
    if "position" not in idea_columns:
        # 手動の並び順。導入前の並び（更新の新しい順）をそのまま初期の順番にする
        conn.execute("ALTER TABLE ideas ADD COLUMN position INTEGER NOT NULL DEFAULT 0")
        ordered = conn.execute("SELECT id FROM ideas ORDER BY updated_at DESC, id DESC").fetchall()
        for position, (idea_id,) in enumerate(ordered):
            conn.execute("UPDATE ideas SET position = ? WHERE id = ?", (position, idea_id))
    # 関連項目が領域の下にあった旧スキーマを、領域と独立した一覧に作り直す
    related_columns = {row[1] for row in conn.execute("PRAGMA table_info(related_items)")}
    if "area_id" in related_columns:
        conn.executescript(
            """CREATE TABLE related_items_new (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   name TEXT NOT NULL UNIQUE
               );
               INSERT INTO related_items_new (name)
                   SELECT name FROM related_items GROUP BY name ORDER BY MIN(id);
               DROP TABLE related_items;
               ALTER TABLE related_items_new RENAME TO related_items;"""
        )
    # 登録制にする前に作られたタスクの領域・関連項目をマスタに取り込む
    conn.execute(
        "INSERT OR IGNORE INTO areas (name) SELECT area FROM tasks GROUP BY area ORDER BY MIN(id)"
    )
    conn.execute(
        """INSERT OR IGNORE INTO related_items (name)
           SELECT related FROM tasks WHERE related != '' GROUP BY related ORDER BY MIN(id)"""
    )
    # メモの日付（後から追加した列）。既存のメモは作成日を入れる
    note_columns = {row[1] for row in conn.execute("PRAGMA table_info(notes)")}
    if "note_date" not in note_columns:
        conn.execute("ALTER TABLE notes ADD COLUMN note_date TEXT NOT NULL DEFAULT ''")
    conn.execute("UPDATE notes SET note_date = substr(created_at, 1, 10) WHERE note_date = ''")
    # 領域の色（後から追加した列）。色のない領域には登録順に自動で割り当てる
    area_columns = {row[1] for row in conn.execute("PRAGMA table_info(areas)")}
    if "color" not in area_columns:
        conn.execute("ALTER TABLE areas ADD COLUMN color TEXT")
    for (area_id,) in conn.execute("SELECT id FROM areas WHERE color IS NULL ORDER BY id").fetchall():
        conn.execute("UPDATE areas SET color = ? WHERE id = ?", (next_color(conn, "areas"), area_id))


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
