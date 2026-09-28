def add(client, text):
    r = client.post("/api/brainstorm", json={"text": text})
    assert r.status_code == 201, r.text
    return r.json()


def test_add_and_list_newest_first(client):
    a = add(client, "一つ目")
    b = add(client, "二つ目")
    assert [x["id"] for x in client.get("/api/brainstorm").json()] == [b["id"], a["id"]]


def test_text_is_stripped(client):
    assert add(client, "  メモ  ")["text"] == "メモ"


def test_blank_text_rejected(client):
    assert client.post("/api/brainstorm", json={"text": "   "}).status_code == 422


def test_delete(client):
    a = add(client, "消す")
    assert client.delete(f"/api/brainstorm/{a['id']}").status_code == 204
    assert client.get("/api/brainstorm").json() == []


def test_promote_creates_idea_and_removes_memo(client):
    a = add(client, "新サービス案")
    r = client.post(f"/api/brainstorm/{a['id']}/promote")
    assert r.status_code == 201
    idea = r.json()
    assert idea["title"] == "新サービス案"
    assert idea["body"] == ""
    assert idea["task_count"] == 0
    assert client.get("/api/brainstorm").json() == []
    assert client.get(f"/api/ideas/{idea['id']}").json() == idea


def test_missing_memo_is_404(client):
    assert client.delete("/api/brainstorm/999").status_code == 404
    assert client.post("/api/brainstorm/999/promote").status_code == 404
