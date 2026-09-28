import pytest

from tests.conftest import register


@pytest.fixture(autouse=True)
def masters(client):
    register(client, "仕事")


def make_idea(client, title="アイディアA", body=""):
    r = client.post("/api/ideas", json={"title": title, "body": body})
    assert r.status_code == 201, r.text
    return r.json()


def test_create_get_and_list(client):
    i = make_idea(client, body="本文")
    assert i["task_count"] == 0
    assert client.get(f"/api/ideas/{i['id']}").json() == i
    assert client.get("/api/ideas").json() == [i]


def test_list_is_newest_updated_first(client):
    a = make_idea(client, "A")
    b = make_idea(client, "B")
    assert [x["id"] for x in client.get("/api/ideas").json()] == [b["id"], a["id"]]
    client.patch(f"/api/ideas/{a['id']}", json={"body": "更新"})
    assert [x["id"] for x in client.get("/api/ideas").json()] == [a["id"], b["id"]]


def test_patch(client):
    i = make_idea(client)
    r = client.patch(f"/api/ideas/{i['id']}", json={"title": "新タイトル"})
    assert r.status_code == 200
    assert r.json()["title"] == "新タイトル"
    assert r.json()["body"] == ""


def test_search_title_and_body(client):
    make_idea(client, "旅行計画", "北海道")
    make_idea(client, "読書メモ", "旅行記を読む")
    make_idea(client, "家計", "")
    titles = {x["title"] for x in client.get("/api/ideas", params={"q": "旅行"}).json()}
    assert titles == {"旅行計画", "読書メモ"}


def test_search_escapes_like_wildcards(client):
    make_idea(client, "達成率100%")
    make_idea(client, "達成率1000")
    make_idea(client, "a_b")
    make_idea(client, "axb")
    assert [x["title"] for x in client.get("/api/ideas", params={"q": "100%"}).json()] == ["達成率100%"]
    assert [x["title"] for x in client.get("/api/ideas", params={"q": "a_b"}).json()] == ["a_b"]


def test_task_count(client):
    i = make_idea(client)
    client.post("/api/tasks", json={
        "area": "仕事", "title": i["title"], "priority": "mid",
        "start_at": "2026-10-01T09:00", "due_at": "2026-10-08T18:00", "idea_id": i["id"],
    })
    assert client.get(f"/api/ideas/{i['id']}").json()["task_count"] == 1
    assert client.get("/api/ideas").json()[0]["task_count"] == 1


def test_delete_idea_keeps_tasks(client):
    i = make_idea(client)
    t = client.post("/api/tasks", json={
        "area": "仕事", "title": "x", "priority": "mid",
        "start_at": "2026-10-01T09:00", "due_at": "2026-10-08T18:00", "idea_id": i["id"],
    }).json()
    assert client.delete(f"/api/ideas/{i['id']}").status_code == 204
    tasks = client.get("/api/tasks").json()
    assert [x["id"] for x in tasks] == [t["id"]]
    assert tasks[0]["idea_id"] is None


def test_missing_idea_is_404(client):
    assert client.get("/api/ideas/999").status_code == 404
    assert client.patch("/api/ideas/999", json={"title": "x"}).status_code == 404
    assert client.delete("/api/ideas/999").status_code == 404


def test_blank_title_rejected(client):
    assert client.post("/api/ideas", json={"title": "  "}).status_code == 422
    i = make_idea(client)
    assert client.patch(f"/api/ideas/{i['id']}", json={"title": " "}).status_code == 422
    assert client.patch(f"/api/ideas/{i['id']}", json={"title": None}).status_code == 422
