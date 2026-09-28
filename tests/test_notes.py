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


def test_pin_and_reorder(client):
    a, b, c = make(client, "# A"), make(client, "# B"), make(client, "# C")
    assert titles(client) == ["C", "B", "A"]
    assert client.post("/api/notes/reorder", json={"ids": [a["id"], c["id"], b["id"]]}).status_code == 204
    assert titles(client) == ["A", "C", "B"]
    client.patch(f"/api/notes/{b['id']}", json={"pinned": True})
    assert titles(client) == ["B", "A", "C"]
    assert client.post("/api/notes/reorder", json={"ids": [a["id"], a["id"]]}).status_code == 422
    assert client.post("/api/notes/reorder", json={"ids": [999]}).status_code == 404


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
