import sqlite3
from pathlib import Path

import pytest

from tests.conftest import OWNER, register


def backups(client):
    r = client.get("/api/backups")
    assert r.status_code == 200, r.text
    return r.json()


def create(client):
    r = client.post("/api/backups")
    assert r.status_code == 201, r.text
    return r.json()


def backup_dir(tmp_path) -> Path:
    return tmp_path / "backups"


def add_task(client, title):
    r = client.post("/api/tasks", json={
        "area": "仕事", "title": title, "priority": "mid",
        "start_at": "2026-10-01T09:00", "due_at": "2026-10-02T09:00",
    })
    assert r.status_code == 201, r.text
    return r.json()


def titles(client):
    return [t["title"] for t in client.get("/api/tasks").json()]


def test_backups_require_login(anon_client):
    assert anon_client.get("/api/backups").status_code == 401
    assert anon_client.post("/api/backups").status_code == 401


def test_create_and_list(client, tmp_path):
    assert backups(client) == []
    b = create(client)
    assert b["name"].startswith("app-") and b["name"].endswith(".db")
    assert b["kind"] == "manual"
    assert b["size"] > 0
    assert (backup_dir(tmp_path) / b["name"]).exists()
    assert [x["name"] for x in backups(client)] == [b["name"]]


def test_several_backups_in_same_second_get_distinct_names(client):
    names = {create(client)["name"] for _ in range(3)}
    assert len(names) == 3
    assert len(backups(client)) == 3


def test_restore_brings_back_data(client):
    register(client, "仕事")
    add_task(client, "バックアップ前のタスク")
    client.post("/api/notes", json={"title": "メモA", "body": "本文"})
    b = create(client)
    # バックアップの後で変更する
    for t in client.get("/api/tasks").json():
        client.delete(f"/api/tasks/{t['id']}")
    add_task(client, "後から作ったタスク")
    r = client.post(f"/api/backups/{b['name']}/restore")
    assert r.status_code == 200, r.text
    assert titles(client) == ["バックアップ前のタスク"]
    assert [n["title"] for n in client.get("/api/notes").json()] == ["メモA"]
    # 戻す前の状態も自動でバックアップされている
    kinds = [x["kind"] for x in backups(client)]
    assert "before-restore" in kinds
    before = next(x for x in backups(client) if x["kind"] == "before-restore")
    client.post(f"/api/backups/{before['name']}/restore")
    assert titles(client) == ["後から作ったタスク"]


def test_restore_keeps_login_account(client):
    b = create(client)
    client.post("/api/auth/password", json={"current": OWNER["password"], "new": "new-password"})
    assert client.post(f"/api/backups/{b['name']}/restore").status_code == 200
    # 復元してもログインしたまま・新しいパスワードのまま
    assert client.get("/api/tasks").status_code == 200
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={**OWNER, "password": "new-password"}).status_code == 200


def test_new_ids_do_not_collide_after_restore(client):
    register(client, "仕事")
    add_task(client, "A")
    b = create(client)
    add_task(client, "B")
    client.post(f"/api/backups/{b['name']}/restore")
    c = add_task(client, "C")
    assert sorted(titles(client)) == ["A", "C"]
    assert client.patch(f"/api/tasks/{c['id']}", json={"title": "C2"}).status_code == 200


def test_restore_old_schema_backup(client, tmp_path):
    # 古い版のアプリで作ったバックアップ（列が足りない・表が無い）も戻せる
    old = backup_dir(tmp_path) / "app-20260920-120000.db"
    old.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(old)
    conn.executescript(
        """CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, area TEXT NOT NULL,
               related TEXT NOT NULL DEFAULT '', title TEXT NOT NULL, start_at TEXT NOT NULL,
               due_at TEXT NOT NULL, priority TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0,
               idea_id INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
           INSERT INTO tasks (area, title, start_at, due_at, priority, created_at, updated_at)
               VALUES ('古い領域', '古いタスク', '2026-09-01T09:00', '2026-09-02T09:00', 'low', 'x', 'x');"""
    )
    conn.commit()
    conn.close()
    r = client.post(f"/api/backups/{old.name}/restore")
    assert r.status_code == 200, r.text
    task = client.get("/api/tasks").json()[0]
    assert task["title"] == "古いタスク" and task["memo"] == "" and task["links"] == []


def test_delete_backup_requires_confirmation(client, tmp_path):
    b = create(client)
    # 確認（消すバックアップの名前）が無い・違うときは消さない
    assert client.delete(f"/api/backups/{b['name']}").status_code == 400
    assert client.delete(f"/api/backups/{b['name']}", params={"confirm": "違う名前.db"}).status_code == 400
    assert (backup_dir(tmp_path) / b["name"]).exists()
    r = client.delete(f"/api/backups/{b['name']}", params={"confirm": b["name"]})
    assert r.status_code == 204
    assert backups(client) == []
    assert not (backup_dir(tmp_path) / b["name"]).exists()


def test_download_backup(client):
    b = create(client)
    r = client.get(f"/api/backups/{b['name']}/download")
    assert r.status_code == 200
    assert r.content.startswith(b"SQLite format 3")
    assert b["name"] in r.headers["content-disposition"]


@pytest.mark.parametrize("name", ["app.db", "..%2Fapp.db", "app-2026.db", "evil.db", "app-20260101-000000.txt"])
def test_invalid_or_missing_names_are_rejected(client, tmp_path, name):
    # 「../」を含む名前は URL の段階で別のパスになり、バックアップの処理まで届かない（404 または 405）
    rejected = {404, 405}
    assert client.post(f"/api/backups/{name}/restore").status_code in rejected
    assert client.delete(f"/api/backups/{name}", params={"confirm": name}).status_code in rejected
    download = client.get(f"/api/backups/{name}/download")
    assert download.status_code in rejected
    assert not download.content.startswith(b"SQLite format 3")
    # 本体のデータベースは消えていない
    assert (tmp_path / "test.db").exists()
    assert client.get("/api/tasks").status_code == 200


def test_backups_older_than_30_days_are_deleted(client, tmp_path):
    from datetime import datetime, timedelta

    d = backup_dir(tmp_path)
    d.mkdir(parents=True, exist_ok=True)
    old = d / f"app-{(datetime.now() - timedelta(days=31)):%Y%m%d-%H%M%S}.db"
    recent = d / f"app-{(datetime.now() - timedelta(days=29)):%Y%m%d-%H%M%S}.db"
    for f in (old, recent):
        sqlite3.connect(f).close()
    names = [x["name"] for x in backups(client)]
    assert recent.name in names and old.name not in names
    assert not old.exists() and recent.exists()
