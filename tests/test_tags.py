import sqlite3

from app.db import init_db


def make_idea(client, title="アイディア", tags=None):
    payload = {"title": title}
    if tags is not None:
        payload["tags"] = tags
    r = client.post("/api/ideas", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def names(idea):
    return [t["name"] for t in idea["tags"]]


def test_idea_without_tags_has_empty_list(client):
    assert make_idea(client)["tags"] == []


def test_create_idea_with_tags_creates_tags_with_colors(client):
    i = make_idea(client, tags=["仕事", "改善"])
    assert names(i) == ["仕事", "改善"]
    for tag in i["tags"]:
        assert tag["color"].startswith("#") and len(tag["color"]) == 7
    assert i["tags"][0]["color"] != i["tags"][1]["color"]
    assert [t["name"] for t in client.get("/api/tags").json()] == ["仕事", "改善"]


def test_tags_are_shared_deduped_and_stripped(client):
    a = make_idea(client, "A", tags=["仕事"])
    b = make_idea(client, "B", tags=[" 仕事 ", "仕事"])
    assert names(b) == ["仕事"]
    assert a["tags"][0]["id"] == b["tags"][0]["id"]
    assert len(client.get("/api/tags").json()) == 1


def test_patch_replaces_tags_and_omitting_keeps_them(client):
    i = make_idea(client, tags=["a", "b"])
    r = client.patch(f"/api/ideas/{i['id']}", json={"body": "本文"})
    assert names(r.json()) == ["a", "b"]
    r = client.patch(f"/api/ideas/{i['id']}", json={"tags": ["b", "c"]})
    assert names(r.json()) == ["b", "c"]
    r = client.patch(f"/api/ideas/{i['id']}", json={"tags": []})
    assert r.json()["tags"] == []


def test_blank_tag_rejected(client):
    assert client.post("/api/ideas", json={"title": "x", "tags": ["  "]}).status_code == 422


def test_filter_ideas_by_tag(client):
    make_idea(client, "A", tags=["仕事"])
    make_idea(client, "B", tags=["趣味"])
    make_idea(client, "C", tags=["仕事", "趣味"])
    got = {i["title"] for i in client.get("/api/ideas", params={"tag": "仕事"}).json()}
    assert got == {"A", "C"}
    got = {i["title"] for i in client.get("/api/ideas", params={"tag": "仕事", "q": "C"}).json()}
    assert got == {"C"}


def test_list_includes_tags(client):
    make_idea(client, "A", tags=["仕事"])
    assert names(client.get("/api/ideas").json()[0]) == ["仕事"]


def test_update_tag_color_and_name(client):
    i = make_idea(client, tags=["仕事"])
    tag_id = i["tags"][0]["id"]
    r = client.patch(f"/api/tags/{tag_id}", json={"color": "#16a34a", "name": "ワーク"})
    assert r.status_code == 200
    assert r.json() == {"id": tag_id, "name": "ワーク", "color": "#16a34a"}
    assert client.get(f"/api/ideas/{i['id']}").json()["tags"][0]["name"] == "ワーク"


def test_invalid_color_rejected(client):
    i = make_idea(client, tags=["仕事"])
    tag_id = i["tags"][0]["id"]
    assert client.patch(f"/api/tags/{tag_id}", json={"color": "red"}).status_code == 422


def test_rename_to_existing_tag_conflicts(client):
    i = make_idea(client, tags=["a", "b"])
    r = client.patch(f"/api/tags/{i['tags'][0]['id']}", json={"name": "b"})
    assert r.status_code == 409


def test_delete_tag_removes_it_from_ideas(client):
    i = make_idea(client, tags=["a", "b"])
    assert client.delete(f"/api/tags/{i['tags'][0]['id']}").status_code == 204
    assert names(client.get(f"/api/ideas/{i['id']}").json()) == ["b"]


def test_delete_idea_keeps_tag(client):
    i = make_idea(client, tags=["a"])
    client.delete(f"/api/ideas/{i['id']}")
    assert [t["name"] for t in client.get("/api/tags").json()] == ["a"]


def test_missing_tag_is_404(client):
    assert client.patch("/api/tags/999", json={"color": "#16a34a"}).status_code == 404
    assert client.delete("/api/tags/999").status_code == 404


def test_existing_db_without_memo_column_is_migrated(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, area TEXT NOT NULL,
           related TEXT NOT NULL DEFAULT '', title TEXT NOT NULL, start_at TEXT NOT NULL,
           due_at TEXT NOT NULL, priority TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0,
           idea_id INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""
    )
    conn.execute(
        "INSERT INTO tasks (area, title, start_at, due_at, priority, created_at, updated_at)"
        " VALUES ('仕事', '既存', '2026-10-01T09:00', '2026-10-02T09:00', 'mid', 'x', 'x')"
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv("APP_DB_PATH", str(path))
    init_db()
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT memo FROM tasks").fetchone() == ("",)
    conn.close()


def test_existing_db_gets_links_column(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, area TEXT NOT NULL,
           related TEXT NOT NULL DEFAULT '', title TEXT NOT NULL, start_at TEXT NOT NULL,
           due_at TEXT NOT NULL, priority TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0,
           idea_id INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""
    )
    conn.execute(
        "INSERT INTO tasks (area, title, start_at, due_at, priority, created_at, updated_at)"
        " VALUES ('仕事', '既存', '2026-10-01T09:00', '2026-10-02T09:00', 'mid', 'x', 'x')"
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv("APP_DB_PATH", str(path))
    init_db()
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT links FROM tasks").fetchone() == ("[]",)
    conn.close()
