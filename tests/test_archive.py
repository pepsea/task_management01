import sqlite3

from app.db import init_db


def make_idea(client, title):
    r = client.post("/api/ideas", json={"title": title, "tags": ["仕事"]})
    assert r.status_code == 201, r.text
    return r.json()


def titles(client, **params):
    return [i["title"] for i in client.get("/api/ideas", params=params).json()]


def test_new_idea_is_not_archived(client):
    assert make_idea(client, "A")["archived_at"] is None


def test_archive_hides_from_default_list(client):
    a = make_idea(client, "A")
    make_idea(client, "B")
    r = client.patch(f"/api/ideas/{a['id']}", json={"archived": True})
    assert r.status_code == 200
    assert r.json()["archived_at"] is not None
    assert titles(client) == ["B"]
    assert titles(client, archived="true") == ["A"]


def test_archive_keeps_content_and_updated_at(client):
    a = make_idea(client, "A")
    client.patch(f"/api/ideas/{a['id']}", json={"body": "本文"})
    before = client.get(f"/api/ideas/{a['id']}").json()
    after = client.patch(f"/api/ideas/{a['id']}", json={"archived": True}).json()
    assert after["body"] == "本文"
    assert after["tags"] == before["tags"]
    assert after["updated_at"] == before["updated_at"]


def test_restore(client):
    a = make_idea(client, "A")
    client.patch(f"/api/ideas/{a['id']}", json={"archived": True})
    r = client.patch(f"/api/ideas/{a['id']}", json={"archived": False})
    assert r.json()["archived_at"] is None
    assert titles(client) == ["A"]
    assert titles(client, archived="true") == []


def test_archived_list_newest_archived_first(client):
    a = make_idea(client, "A")
    b = make_idea(client, "B")
    client.patch(f"/api/ideas/{b['id']}", json={"archived": True})
    client.patch(f"/api/ideas/{a['id']}", json={"archived": True})
    assert titles(client, archived="true") == ["A", "B"]


def test_search_and_tag_filter_work_in_archive(client):
    a = make_idea(client, "旅行計画")
    b = make_idea(client, "読書")
    for i in (a, b):
        client.patch(f"/api/ideas/{i['id']}", json={"archived": True})
    assert titles(client, archived="true", q="旅行") == ["旅行計画"]
    assert set(titles(client, archived="true", tag="仕事")) == {"旅行計画", "読書"}


def test_null_archived_rejected(client):
    a = make_idea(client, "A")
    assert client.patch(f"/api/ideas/{a['id']}", json={"archived": None}).status_code == 422


def test_existing_db_gets_archived_at_column(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE ideas (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
           body TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""
    )
    conn.execute("INSERT INTO ideas (title, created_at, updated_at) VALUES ('既存', 'x', 'x')")
    conn.commit()
    conn.close()
    monkeypatch.setenv("APP_DB_PATH", str(path))
    init_db()
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT archived_at FROM ideas").fetchone() == (None,)
    conn.close()
