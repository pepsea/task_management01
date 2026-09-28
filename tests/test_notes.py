import pytest


def make(client, body="# メモ", tags=None):
    payload = {"body": body}
    if tags is not None:
        payload["tags"] = tags
    r = client.post("/api/notes", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def titles(client, **params):
    return [n["title"] for n in client.get("/api/notes", params=params).json()]


@pytest.mark.parametrize("body,title", [
    ("# 会議メモ\n本文", "会議メモ"),
    ("\n\n## 見出し2", "見出し2"),
    ("- [ ] やること", "やること"),
    ("**太字の**タイトル", "太字のタイトル"),
    ("> 引用", "引用"),
    ("```\ncode\n```\n本文", "本文"),
    ("", "無題"),
    ("   \n  ", "無題"),
])
def test_title_is_derived_from_first_line(client, body, title):
    assert make(client, body)["title"] == title


def test_long_title_is_cut(client):
    assert len(make(client, "あ" * 300)["title"]) == 100


def test_create_get_update_delete(client):
    n = make(client, "# A\n本文", tags=["仕事"])
    assert n["body"] == "# A\n本文"
    assert [t["name"] for t in n["tags"]] == ["仕事"]
    assert n["pinned"] is False and n["archived_at"] is None
    assert client.get(f"/api/notes/{n['id']}").json() == n
    r = client.patch(f"/api/notes/{n['id']}", json={"body": "# B"})
    assert r.json()["title"] == "B"
    assert r.json()["tags"] == n["tags"]
    assert client.delete(f"/api/notes/{n['id']}").status_code == 204
    assert client.get(f"/api/notes/{n['id']}").status_code == 404


def test_new_note_on_top_and_update_keeps_order(client):
    a = make(client, "# A")
    make(client, "# B")
    client.patch(f"/api/notes/{a['id']}", json={"body": "# A2"})
    assert titles(client) == ["B", "A2"]


def test_search_and_tag_filter(client):
    make(client, "# 旅行\n北海道", tags=["私用"])
    make(client, "# 会議\n旅行の予算", tags=["仕事"])
    make(client, "# 読書")
    assert set(titles(client, q="旅行")) == {"旅行", "会議"}
    assert titles(client, tag="仕事") == ["会議"]
    assert titles(client, q="100%") == []


def test_list_is_sorted_by_date_with_pinned_first(client):
    def note(title, day):
        return client.post("/api/notes", json={"body": f"# {title}", "note_date": day}).json()

    old = note("古い", "2026-09-01")
    note("新しい", "2026-10-10")
    note("中間", "2026-09-20")
    note("中間2", "2026-09-20")
    # 日付の新しい順。同じ日付は後から作ったものが上
    assert titles(client) == ["新しい", "中間2", "中間", "古い"]
    client.patch(f"/api/notes/{old['id']}", json={"pinned": True})
    assert titles(client) == ["古い", "新しい", "中間2", "中間"]
    # 日付を変えると並びも変わる
    client.patch(f"/api/notes/{old['id']}", json={"pinned": False, "note_date": "2026-12-01"})
    assert titles(client) == ["古い", "新しい", "中間2", "中間"]


def test_archive_and_restore(client):
    a = make(client, "# A")
    make(client, "# B")
    r = client.patch(f"/api/notes/{a['id']}", json={"archived": True})
    assert r.json()["archived_at"] is not None
    assert r.json()["updated_at"] == a["updated_at"]
    assert titles(client) == ["B"]
    assert titles(client, archived="true") == ["A"]
    client.patch(f"/api/notes/{a['id']}", json={"archived": False})
    assert titles(client, archived="true") == []


def test_null_fields_rejected(client):
    n = make(client)
    for field in ["body", "tags", "pinned", "archived"]:
        assert client.patch(f"/api/notes/{n['id']}", json={field: None}).status_code == 422


def test_missing_note_is_404(client):
    assert client.get("/api/notes/999").status_code == 404
    assert client.patch("/api/notes/999", json={"body": "x"}).status_code == 404
    assert client.delete("/api/notes/999").status_code == 404


def test_tags_are_shared_with_ideas(client):
    make(client, "# A", tags=["共通"])
    client.post("/api/ideas", json={"title": "i", "tags": ["共通"]})
    assert [t["name"] for t in client.get("/api/tags").json()] == ["共通"]


def test_deleting_tag_removes_it_from_notes(client):
    n = make(client, "# A", tags=["x", "y"])
    client.delete(f"/api/tags/{n['tags'][0]['id']}")
    assert [t["name"] for t in client.get(f"/api/notes/{n['id']}").json()["tags"]] == ["y"]


def test_note_date_defaults_to_today(client):
    from datetime import date

    assert make(client)["note_date"] == date.today().isoformat()


def test_note_date_can_be_set_and_changed(client):
    r = client.post("/api/notes", json={"body": "# A", "note_date": "2026-10-01"})
    assert r.json()["note_date"] == "2026-10-01"
    r = client.patch(f"/api/notes/{r.json()['id']}", json={"note_date": "2026-12-24"})
    assert r.status_code == 200
    assert r.json()["note_date"] == "2026-12-24"


@pytest.mark.parametrize("value", ["2026/10/01", "2026-02-30", "", None])
def test_invalid_note_date_rejected(client, value):
    n = make(client)
    assert client.patch(f"/api/notes/{n['id']}", json={"note_date": value}).status_code == 422


def test_existing_notes_get_date_from_created_at(tmp_path, monkeypatch):
    import sqlite3

    from app.db import init_db

    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE notes (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
           body TEXT NOT NULL DEFAULT '', pinned INTEGER NOT NULL DEFAULT 0,
           position INTEGER NOT NULL DEFAULT 0, archived_at TEXT,
           created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""
    )
    conn.execute(
        "INSERT INTO notes (title, created_at, updated_at) VALUES ('既存', '2026-09-15T10:00:00', 'x')"
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv("APP_DB_PATH", str(path))
    init_db()
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT note_date FROM notes").fetchone() == ("2026-09-15",)
    conn.close()


def test_manual_sort_and_reorder(client):
    def note(title, day):
        return client.post("/api/notes", json={"body": f"# {title}", "note_date": day}).json()["id"]

    a = note("A", "2026-09-01")
    b = note("B", "2026-10-01")
    c = note("C", "2026-09-15")
    # 手動の初期の並びは作った順（新しいものが上）
    assert titles(client, sort="manual") == ["C", "B", "A"]
    assert client.post("/api/notes/reorder", json={"ids": [a, c, b]}).status_code == 204
    assert titles(client, sort="manual") == ["A", "C", "B"]
    # 日付順は並べ替えの影響を受けない
    assert titles(client) == ["B", "C", "A"]
    assert titles(client, sort="date") == ["B", "C", "A"]
    client.patch(f"/api/notes/{b}", json={"pinned": True})
    assert titles(client, sort="manual") == ["B", "A", "C"]


def test_new_note_goes_top_in_manual_sort(client):
    a = client.post("/api/notes", json={"body": "# A"}).json()["id"]
    b = client.post("/api/notes", json={"body": "# B"}).json()["id"]
    client.post("/api/notes/reorder", json={"ids": [a, b]})
    client.post("/api/notes", json={"body": "# C"})
    assert titles(client, sort="manual") == ["C", "A", "B"]


def test_reorder_notes_rejects_bad_ids(client):
    a = client.post("/api/notes", json={"body": "# A"}).json()["id"]
    assert client.post("/api/notes/reorder", json={"ids": [a, a]}).status_code == 422
    assert client.post("/api/notes/reorder", json={"ids": [999]}).status_code == 404
    assert client.post("/api/notes/reorder", json={"ids": []}).status_code == 422


def test_invalid_sort_rejected(client):
    assert client.get("/api/notes", params={"sort": "title"}).status_code == 422
