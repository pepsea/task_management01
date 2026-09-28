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


def areas(client):
    return client.get("/api/areas").json()


def test_create_area_and_related(client):
    r = client.post("/api/areas", json={"name": "仕事"})
    assert r.status_code == 201
    area = r.json()
    assert area["name"] == "仕事"
    assert area["related"] == []
    r = client.post(f"/api/areas/{area['id']}/related", json={"name": "PJ-A"})
    assert r.status_code == 201
    assert r.json()["name"] == "PJ-A"
    assert r.json()["area_id"] == area["id"]
    assert [(a["name"], [x["name"] for x in a["related"]]) for a in areas(client)] == [("仕事", ["PJ-A"])]


def test_areas_keep_registration_order(client):
    register(client, "仕事")
    register(client, "プライベート")
    register(client, "学習")
    assert [a["name"] for a in areas(client)] == ["仕事", "プライベート", "学習"]


def test_duplicate_names_conflict(client):
    area_id = register(client, "仕事", "PJ-A")
    assert client.post("/api/areas", json={"name": " 仕事 "}).status_code == 409
    assert client.post(f"/api/areas/{area_id}/related", json={"name": "PJ-A"}).status_code == 409


def test_same_related_name_allowed_in_other_area(client):
    register(client, "仕事", "共通")
    register(client, "プライベート", "共通")
    assert [len(a["related"]) for a in areas(client)] == [1, 1]


def test_blank_names_rejected(client):
    assert client.post("/api/areas", json={"name": "  "}).status_code == 422
    area_id = register(client, "仕事")
    assert client.post(f"/api/areas/{area_id}/related", json={"name": ""}).status_code == 422


def test_task_requires_registered_area_and_related(client):
    assert client.post("/api/tasks", json=task_payload()).status_code == 422
    register(client, "仕事")
    assert client.post("/api/tasks", json=task_payload()).status_code == 422
    assert client.post("/api/tasks", json=task_payload(related="")).status_code == 201
    register(client, "仕事", "PJ-A")
    assert client.post("/api/tasks", json=task_payload()).status_code == 201


def test_related_must_belong_to_task_area(client):
    register(client, "仕事", "PJ-A")
    register(client, "プライベート")
    assert client.post("/api/tasks", json=task_payload(area="プライベート")).status_code == 422
    t = client.post("/api/tasks", json=task_payload()).json()
    r = client.patch(f"/api/tasks/{t['id']}", json={"area": "プライベート"})
    assert r.status_code == 422


def test_rename_area_updates_tasks(client):
    area_id = register(client, "仕事", "PJ-A")
    t = client.post("/api/tasks", json=task_payload()).json()
    r = client.patch(f"/api/areas/{area_id}", json={"name": "本業"})
    assert r.status_code == 200
    assert r.json()["name"] == "本業"
    assert client.get("/api/tasks").json()[0]["area"] == "本業"
    assert client.get("/api/tasks").json()[0]["id"] == t["id"]


def test_rename_related_updates_only_that_area(client):
    work = register(client, "仕事", "共通")
    register(client, "プライベート", "共通")
    client.post("/api/tasks", json=task_payload(related="共通", title="w"))
    client.post("/api/tasks", json=task_payload(area="プライベート", related="共通", title="p"))
    related_id = next(a for a in areas(client) if a["id"] == work)["related"][0]["id"]
    r = client.patch(f"/api/related/{related_id}", json={"name": "PJ-B"})
    assert r.status_code == 200
    got = {t["title"]: t["related"] for t in client.get("/api/tasks").json()}
    assert got == {"w": "PJ-B", "p": "共通"}


def test_rename_to_existing_name_conflicts(client):
    register(client, "仕事", "PJ-A", "PJ-B")
    register(client, "プライベート")
    work = areas(client)[0]
    assert client.patch(f"/api/areas/{work['id']}", json={"name": "プライベート"}).status_code == 409
    pj_a = work["related"][0]
    assert client.patch(f"/api/related/{pj_a['id']}", json={"name": "PJ-B"}).status_code == 409


def test_delete_unused_area_and_related(client):
    area_id = register(client, "仕事", "PJ-A")
    related_id = areas(client)[0]["related"][0]["id"]
    assert client.delete(f"/api/related/{related_id}").status_code == 204
    assert areas(client)[0]["related"] == []
    assert client.delete(f"/api/areas/{area_id}").status_code == 204
    assert areas(client) == []


def test_delete_area_removes_its_related(client):
    area_id = register(client, "仕事", "PJ-A")
    assert client.delete(f"/api/areas/{area_id}").status_code == 204
    register(client, "仕事")
    assert areas(client)[0]["related"] == []


def test_cannot_delete_area_or_related_in_use(client):
    area_id = register(client, "仕事", "PJ-A")
    client.post("/api/tasks", json=task_payload())
    related_id = areas(client)[0]["related"][0]["id"]
    assert client.delete(f"/api/areas/{area_id}").status_code == 409
    assert client.delete(f"/api/related/{related_id}").status_code == 409


def test_missing_master_is_404(client):
    assert client.patch("/api/areas/999", json={"name": "x"}).status_code == 404
    assert client.delete("/api/areas/999").status_code == 404
    assert client.post("/api/areas/999/related", json={"name": "x"}).status_code == 404
    assert client.patch("/api/related/999", json={"name": "x"}).status_code == 404
    assert client.delete("/api/related/999").status_code == 404


def test_existing_task_values_are_registered_on_startup(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    monkeypatch.setenv("APP_DB_PATH", str(path))
    init_db()
    conn = sqlite3.connect(path)
    for area, related in [("仕事", "PJ-A"), ("仕事", ""), ("プライベート", "引越し")]:
        conn.execute(
            "INSERT INTO tasks (area, related, title, start_at, due_at, priority, created_at, updated_at)"
            " VALUES (?, ?, 't', '2026-10-01T09:00', '2026-10-02T09:00', 'mid', 'x', 'x')",
            (area, related),
        )
    conn.commit()
    conn.close()
    init_db()
    init_db()  # 2 回目でも重複登録しない
    conn = sqlite3.connect(path)
    got = conn.execute(
        """SELECT a.name, r.name FROM areas a LEFT JOIN related_items r ON r.area_id = a.id
           ORDER BY a.id, r.id"""
    ).fetchall()
    conn.close()
    assert got == [("仕事", "PJ-A"), ("プライベート", "引越し")]
