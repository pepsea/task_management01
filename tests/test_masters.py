import sqlite3

from app.db import init_db
from tests.conftest import register


def task_payload(**overrides):
    payload = {
        "area": "仕事", "related": "PJ-A", "title": "x", "priority": "mid",
        "start_at": "2026-10-01T09:00", "due_at": "2026-10-02T09:00",
    }
    payload.update(overrides)
    return payload


def names(client, path):
    return [x["name"] for x in client.get(path).json()]


def test_create_area_and_related_independently(client):
    r = client.post("/api/areas", json={"name": "仕事"})
    assert r.status_code == 201
    assert set(r.json()) == {"id", "name"}
    r = client.post("/api/related", json={"name": "PJ-A"})
    assert r.status_code == 201
    assert set(r.json()) == {"id", "name"}
    assert names(client, "/api/areas") == ["仕事"]
    assert names(client, "/api/related") == ["PJ-A"]


def test_lists_keep_registration_order(client):
    register(client, "仕事", "PJ-B", "PJ-A")
    register(client, "プライベート")
    register(client, "学習")
    assert names(client, "/api/areas") == ["仕事", "プライベート", "学習"]
    assert names(client, "/api/related") == ["PJ-B", "PJ-A"]


def test_duplicate_names_conflict(client):
    register(client, "仕事", "PJ-A")
    assert client.post("/api/areas", json={"name": " 仕事 "}).status_code == 409
    assert client.post("/api/related", json={"name": "PJ-A"}).status_code == 409


def test_blank_names_rejected(client):
    assert client.post("/api/areas", json={"name": "  "}).status_code == 422
    assert client.post("/api/related", json={"name": ""}).status_code == 422


def test_task_requires_registered_area_and_related(client):
    assert client.post("/api/tasks", json=task_payload()).status_code == 422
    register(client, "仕事")
    assert client.post("/api/tasks", json=task_payload()).status_code == 422
    assert client.post("/api/tasks", json=task_payload(related="")).status_code == 201
    register(client, None, "PJ-A")
    assert client.post("/api/tasks", json=task_payload()).status_code == 201


def test_any_related_can_be_used_with_any_area(client):
    register(client, "仕事", "PJ-A")
    register(client, "プライベート")
    assert client.post("/api/tasks", json=task_payload(area="プライベート")).status_code == 201


def test_patch_with_unregistered_values_rejected(client):
    register(client, "仕事", "PJ-A")
    t = client.post("/api/tasks", json=task_payload()).json()
    assert client.patch(f"/api/tasks/{t['id']}", json={"area": "未登録"}).status_code == 422
    assert client.patch(f"/api/tasks/{t['id']}", json={"related": "未登録"}).status_code == 422


def test_rename_area_updates_tasks(client):
    register(client, "仕事", "PJ-A")
    client.post("/api/tasks", json=task_payload())
    area_id = client.get("/api/areas").json()[0]["id"]
    r = client.patch(f"/api/areas/{area_id}", json={"name": "本業"})
    assert r.status_code == 200
    assert r.json()["name"] == "本業"
    assert client.get("/api/tasks").json()[0]["area"] == "本業"


def test_rename_related_updates_tasks_in_all_areas(client):
    register(client, "仕事", "共通")
    register(client, "プライベート")
    client.post("/api/tasks", json=task_payload(related="共通", title="w"))
    client.post("/api/tasks", json=task_payload(area="プライベート", related="共通", title="p"))
    related_id = client.get("/api/related").json()[0]["id"]
    r = client.patch(f"/api/related/{related_id}", json={"name": "横断"})
    assert r.status_code == 200
    assert {t["title"]: t["related"] for t in client.get("/api/tasks").json()} == {"w": "横断", "p": "横断"}


def test_rename_to_existing_name_conflicts(client):
    register(client, "仕事", "PJ-A", "PJ-B")
    register(client, "プライベート")
    area_id = client.get("/api/areas").json()[0]["id"]
    assert client.patch(f"/api/areas/{area_id}", json={"name": "プライベート"}).status_code == 409
    related_id = client.get("/api/related").json()[0]["id"]
    assert client.patch(f"/api/related/{related_id}", json={"name": "PJ-B"}).status_code == 409


def test_delete_unused_area_and_related(client):
    register(client, "仕事", "PJ-A")
    area_id = client.get("/api/areas").json()[0]["id"]
    related_id = client.get("/api/related").json()[0]["id"]
    assert client.delete(f"/api/related/{related_id}").status_code == 204
    assert client.delete(f"/api/areas/{area_id}").status_code == 204
    assert client.get("/api/areas").json() == []
    assert client.get("/api/related").json() == []


def test_deleting_area_keeps_related(client):
    register(client, "仕事", "PJ-A")
    area_id = client.get("/api/areas").json()[0]["id"]
    client.delete(f"/api/areas/{area_id}")
    assert names(client, "/api/related") == ["PJ-A"]


def test_cannot_delete_area_or_related_in_use(client):
    register(client, "仕事", "PJ-A")
    client.post("/api/tasks", json=task_payload())
    area_id = client.get("/api/areas").json()[0]["id"]
    related_id = client.get("/api/related").json()[0]["id"]
    assert client.delete(f"/api/areas/{area_id}").status_code == 409
    assert client.delete(f"/api/related/{related_id}").status_code == 409


def test_missing_master_is_404(client):
    assert client.patch("/api/areas/999", json={"name": "x"}).status_code == 404
    assert client.delete("/api/areas/999").status_code == 404
    assert client.patch("/api/related/999", json={"name": "x"}).status_code == 404
    assert client.delete("/api/related/999").status_code == 404


def _insert_task(conn, area, related):
    conn.execute(
        "INSERT INTO tasks (area, related, title, start_at, due_at, priority, created_at, updated_at)"
        " VALUES (?, ?, 't', '2026-10-01T09:00', '2026-10-02T09:00', 'mid', 'x', 'x')",
        (area, related),
    )


def test_existing_task_values_are_registered_on_startup(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    monkeypatch.setenv("APP_DB_PATH", str(path))
    init_db()
    conn = sqlite3.connect(path)
    for area, related in [("仕事", "PJ-A"), ("仕事", ""), ("プライベート", "引越し"), ("学習", "PJ-A")]:
        _insert_task(conn, area, related)
    conn.commit()
    conn.close()
    init_db()
    init_db()  # 2 回目でも重複登録しない
    conn = sqlite3.connect(path)
    areas = [r[0] for r in conn.execute("SELECT name FROM areas ORDER BY id")]
    related = [r[0] for r in conn.execute("SELECT name FROM related_items ORDER BY id")]
    conn.close()
    assert areas == ["仕事", "プライベート", "学習"]
    assert related == ["PJ-A", "引越し"]


def test_hierarchical_related_table_is_migrated(tmp_path, monkeypatch):
    # 関連項目が領域の下にあった旧スキーマから、独立した一覧に移行する
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """CREATE TABLE areas (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE);
           CREATE TABLE related_items (id INTEGER PRIMARY KEY AUTOINCREMENT,
               area_id INTEGER NOT NULL REFERENCES areas(id) ON DELETE CASCADE,
               name TEXT NOT NULL, UNIQUE (area_id, name));
           INSERT INTO areas (name) VALUES ('仕事'), ('プライベート');
           INSERT INTO related_items (area_id, name) VALUES (1, 'PJ-A'), (1, '共通'), (2, '共通');"""
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv("APP_DB_PATH", str(path))
    init_db()
    conn = sqlite3.connect(path)
    columns = {r[1] for r in conn.execute("PRAGMA table_info(related_items)")}
    related = [r[0] for r in conn.execute("SELECT name FROM related_items ORDER BY id")]
    conn.close()
    assert "area_id" not in columns
    assert related == ["PJ-A", "共通"]
