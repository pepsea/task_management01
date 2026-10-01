"""データベースのバックアップ（data/backups/）と復元。バックアップは 30 日で自動削除する。"""

import re
import shutil
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path

from app.db import SCHEMA, _migrate, connect, db_path

RETENTION_DAYS = 30
# app-YYYYMMDD-HHMMSS[-before-restore][-N].db
NAME_PATTERN = re.compile(r"^app-(\d{8}-\d{6})(-before-restore)?(?:-(\d+))?\.db$")

# 復元で中身を入れ替える表（外部キーの親から順に）。ログインのアカウントとセッションは入れ替えない
DATA_TABLES = [
    "areas", "related_items", "tags", "ideas", "idea_tags", "notes", "note_tags",
    "recurring_tasks", "tasks", "decisions", "brainstorm", "quick_links",
]


def backup_dir() -> Path:
    return db_path().parent / "backups"


def _parse(name: str) -> tuple[datetime, str] | None:
    m = NAME_PATTERN.match(name)
    if not m:
        return None
    try:
        created = datetime.strptime(m.group(1), "%Y%m%d-%H%M%S")
    except ValueError:
        return None
    return created, ("before-restore" if m.group(2) else "manual")


def _info(path: Path) -> dict:
    created, kind = _parse(path.name)
    return {
        "name": path.name,
        "kind": kind,
        "created_at": created.isoformat(),
        "size": path.stat().st_size,
    }


def find_backup(name: str) -> Path | None:
    """名前の形が正しく、実在するバックアップだけを返す（フォルダの外を指す名前は通さない）。"""
    if _parse(name) is None:
        return None
    path = backup_dir() / name
    return path if path.is_file() else None


def delete_expired(now: datetime | None = None) -> None:
    """作成から 30 日を過ぎたバックアップを削除する。"""
    folder = backup_dir()
    if not folder.is_dir():
        return
    limit = (now or datetime.now()) - timedelta(days=RETENTION_DAYS)
    for path in folder.iterdir():
        parsed = _parse(path.name)
        if parsed and parsed[0] < limit:
            path.unlink(missing_ok=True)


def list_backups() -> list[dict]:
    delete_expired()
    folder = backup_dir()
    if not folder.is_dir():
        return []
    items = [_info(p) for p in folder.iterdir() if p.is_file() and _parse(p.name)]
    return sorted(items, key=lambda b: (b["created_at"], b["name"]), reverse=True)


def create_backup(kind: str = "manual") -> dict:
    folder = backup_dir()
    folder.mkdir(parents=True, exist_ok=True)
    delete_expired()
    stem = f"app-{datetime.now():%Y%m%d-%H%M%S}" + ("-before-restore" if kind == "before-restore" else "")
    path = folder / f"{stem}.db"
    counter = 1
    while path.exists():
        counter += 1
        path = folder / f"{stem}-{counter}.db"
    # SQLite のバックアップ機能で、使用中でも整合の取れた状態を写す
    with closing(connect()) as src, closing(sqlite3.connect(path)) as dst:
        src.backup(dst)
    return _info(path)


def _columns(conn: sqlite3.Connection, schema: str, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA {schema}.table_info({table})")]


def restore_backup(path: Path) -> dict:
    """バックアップの時点のデータに戻す。戻す前の状態は自動でバックアップしておく。"""
    before = create_backup("before-restore")
    with tempfile.TemporaryDirectory() as tmp:
        # 古い版のアプリで作ったバックアップでも戻せるよう、写しを今の表の形に合わせる
        copy = Path(tmp) / "restore.db"
        shutil.copyfile(path, copy)
        with closing(sqlite3.connect(copy)) as old:
            old.executescript(SCHEMA)
            _migrate(old)
            old.commit()

        with closing(connect()) as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("ATTACH DATABASE ? AS bk", (str(copy),))
            try:
                for table in reversed(DATA_TABLES):
                    conn.execute(f"DELETE FROM main.{table}")
                for table in DATA_TABLES:
                    backup_columns = set(_columns(conn, "bk", table))
                    columns = [c for c in _columns(conn, "main", table) if c in backup_columns]
                    names = ", ".join(columns)
                    conn.execute(f"INSERT INTO main.{table} ({names}) SELECT {names} FROM bk.{table}")
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.execute("DETACH DATABASE bk")
                conn.execute("PRAGMA foreign_keys = ON")
    return before
