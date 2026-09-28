import sqlite3

from app.db import init_db


def make(client, title):
    r = client.post("/api/ideas", json={"title": title})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def titles(client, **params):
    return [i["title"] for i in client.get("/api/ideas", params=params).json()]


def reorder(client, ids):
    return client.post("/api/ideas/reorder", json={"ids": ids})


def test_reorder_full_list(client):
    a, b, c = make(client, "A"), make(client, "B"), make(client, "C")
    assert titles(client) == ["C", "B", "A"]
    r = reorder(client, [a, c, b])
    assert r.status_code == 204
    assert titles(client) == ["A", "C", "B"]


def test_reorder_subset_keeps_other_positions(client):
    a, b, c, d = make(client, "A"), make(client, "B"), make(client, "C"), make(client, "D")
    assert titles(client) == ["D", "C", "B", "A"]
    # 絞り込みで D と B だけが見えている状態で入れ替えても、C と A の位置は変わらない
    assert reorder(client, [b, d]).status_code == 204
    assert titles(client) == ["B", "C", "D", "A"]


def test_prioritized_group_stays_first(client):
    a, b, c = make(client, "A"), make(client, "B"), make(client, "C")
    client.patch(f"/api/ideas/{a}", json={"prioritized": True})
    reorder(client, [b, c])
    assert titles(client) == ["A", "B", "C"]


def test_new_idea_goes_top_after_reorder(client):
    a, b = make(client, "A"), make(client, "B")
    reorder(client, [a, b])
    make(client, "C")
    assert titles(client) == ["C", "A", "B"]


def test_promoted_memo_goes_top(client):
    a, b = make(client, "A"), make(client, "B")
    reorder(client, [a, b])
    memo = client.post("/api/brainstorm", json={"text": "メモ"}).json()
    client.post(f"/api/brainstorm/{memo['id']}/promote")
    assert titles(client) == ["メモ", "A", "B"]


def test_priority_toggle_keeps_position_within_group(client):
    a, b, c = make(client, "A"), make(client, "B"), make(client, "C")
    reorder(client, [a, b, c])
    client.patch(f"/api/ideas/{b}", json={"prioritized": True})
    client.patch(f"/api/ideas/{b}", json={"prioritized": False})
    assert titles(client) == ["A", "B", "C"]


def test_reorder_rejects_unknown_or_duplicate_ids(client):
    a, b = make(client, "A"), make(client, "B")
    assert reorder(client, [a, 999]).status_code == 404
    assert reorder(client, [a, a]).status_code == 422
    assert reorder(client, []).status_code == 422
    assert titles(client) == ["B", "A"]


def test_existing_ideas_get_positions_in_updated_order(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        """CREATE TABLE ideas (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
           body TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"""
    )
    for title, updated in [("古い", "2026-09-01"), ("新しい", "2026-09-20"), ("中間", "2026-09-10")]:
        conn.execute(
            "INSERT INTO ideas (title, created_at, updated_at) VALUES (?, 'x', ?)", (title, updated)
        )
    conn.commit()
    conn.close()
    monkeypatch.setenv("APP_DB_PATH", str(path))
    init_db()
    init_db()
    conn = sqlite3.connect(path)
    got = [r[0] for r in conn.execute("SELECT title FROM ideas ORDER BY position")]
    conn.close()
    assert got == ["新しい", "中間", "古い"]
