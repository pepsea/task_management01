import csv
import io
import sqlite3
from datetime import datetime, timedelta

import pytest

from app.db import db_path
from tests.conftest import register
from tests.test_tasks import make_task


@pytest.fixture(autouse=True)
def masters(client):
    register(client, "仕事", "PJ-A")


def set_done_at(task_id, when):
    with sqlite3.connect(db_path()) as conn:
        conn.execute("UPDATE tasks SET done_at = ? WHERE id = ?", (when.isoformat(), task_id))


def ids(tasks):
    return [t["id"] for t in tasks]


def test_done_at_is_recorded_and_cleared(client):
    t = make_task(client)
    assert t["done_at"] is None
    done = client.patch(f"/api/tasks/{t['id']}", json={"done": True}).json()
    assert done["done_at"] is not None
    # 完了のまま保存し直しても完了日時は変わらない
    again = client.patch(f"/api/tasks/{t['id']}", json={"done": True, "title": "改題"}).json()
    assert again["done_at"] == done["done_at"]
    undone = client.patch(f"/api/tasks/{t['id']}", json={"done": False}).json()
    assert undone["done_at"] is None


def test_created_as_done_has_done_at(client):
    assert make_task(client, done=True)["done_at"] is not None


def test_done_task_moves_to_archive_after_two_days(client):
    recent = make_task(client, title="昨日完了", done=True)
    old = make_task(client, title="3日前に完了", done=True)
    open_task = make_task(client, title="未完了")
    set_done_at(recent["id"], datetime.now() - timedelta(days=1))
    set_done_at(old["id"], datetime.now() - timedelta(days=3))

    assert set(ids(client.get("/api/tasks").json())) == {recent["id"], open_task["id"]}
    assert ids(client.get("/api/tasks/archived").json()) == [old["id"]]
    assert ids(client.get("/api/tasks", params={"area": "仕事"}).json()) == ids(client.get("/api/tasks").json())


def test_archive_is_newest_first_and_searchable(client):
    a = make_task(client, title="古い", done=True, memo="議事録")
    b = make_task(client, title="新しい", done=True)
    set_done_at(a["id"], datetime.now() - timedelta(days=30))
    set_done_at(b["id"], datetime.now() - timedelta(days=5))
    assert ids(client.get("/api/tasks/archived").json()) == [b["id"], a["id"]]
    assert ids(client.get("/api/tasks/archived", params={"q": "議事録"}).json()) == [a["id"]]


def test_restore_from_archive_returns_to_todo(client):
    t = make_task(client, done=True)
    set_done_at(t["id"], datetime.now() - timedelta(days=10))
    client.patch(f"/api/tasks/{t['id']}", json={"done": False})
    assert client.get("/api/tasks/archived").json() == []
    assert ids(client.get("/api/tasks").json()) == [t["id"]]


def test_archived_tasks_are_deleted_after_one_year(client):
    kept = make_task(client, title="300日前", done=True)
    expired = make_task(client, title="400日前", done=True)
    set_done_at(kept["id"], datetime.now() - timedelta(days=300))
    set_done_at(expired["id"], datetime.now() - timedelta(days=400))
    assert ids(client.get("/api/tasks/archived").json()) == [kept["id"]]
    with sqlite3.connect(db_path()) as conn:
        assert conn.execute("SELECT COUNT(*) FROM tasks WHERE id = ?", (expired["id"],)).fetchone()[0] == 0


def test_open_tasks_are_never_expired(client):
    t = make_task(client, start_at="2020-01-01T09:00", due_at="2020-01-02T18:00")
    assert ids(client.get("/api/tasks").json()) == [t["id"]]


def test_archived_csv_export(client):
    t = make_task(client, title="報告書", done=True, memo="メモ")
    make_task(client, title="未完了")
    set_done_at(t["id"], datetime.now() - timedelta(days=3))
    r = client.get("/api/tasks/archived.csv")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert rows[0][:3] == ["領域", "関連項目", "タスク名"]
    assert "完了日時" in rows[0]
    assert [row[2] for row in rows[1:]] == ["報告書"]


def test_migration_fills_done_at_for_existing_done_tasks(client):
    from app.db import _migrate

    t = make_task(client, done=True)
    with sqlite3.connect(db_path()) as conn:
        conn.execute("ALTER TABLE tasks DROP COLUMN done_at")
        _migrate(conn)
        row = conn.execute("SELECT done_at, updated_at FROM tasks WHERE id = ?", (t["id"],)).fetchone()
    assert row[0] == row[1]


def test_todo_csv_export(client):
    late = make_task(client, title="後", due_at="2026-10-09T18:00", priority="low")
    early = make_task(client, title="先", due_at="2026-10-03T18:00")
    done = make_task(client, title="完了済み", done=True)
    old = make_task(client, title="アーカイブ済み", done=True)
    set_done_at(old["id"], datetime.now() - timedelta(days=5))
    r = client.get("/api/tasks.csv")
    assert r.status_code == 200
    assert r.content.startswith(b"\xef\xbb\xbf")
    assert "attachment" in r.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(r.content.decode("utf-8-sig"))))
    assert rows[0][:3] == ["領域", "関連項目", "タスク名"]
    # 未完了は期限の近い順、完了は最後。アーカイブに移ったものは入れない
    assert [row[2] for row in rows[1:]] == ["先", "後", "完了済み"]
