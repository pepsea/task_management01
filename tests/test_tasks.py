import pytest

from tests.conftest import register


@pytest.fixture(autouse=True)
def masters(client):
    register(client, "仕事", "PJ-A")
    register(client, "プライベート")
    register(client, "a")
    register(client, "b")


def make_task(client, **overrides):
    payload = {
        "area": "仕事",
        "related": "PJ-A",
        "title": "資料作成",
        "start_at": "2026-09-28T09:00",
        "due_at": "2026-10-02T18:00",
        "priority": "high",
    }
    payload.update(overrides)
    r = client.post("/api/tasks", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_and_list(client):
    t = make_task(client)
    assert t["id"] > 0
    assert t["done"] is False
    assert t["idea_id"] is None
    assert client.get("/api/tasks").json() == [t]


def test_list_is_ordered_by_start(client):
    b = make_task(client, title="B", start_at="2026-10-05T09:00", due_at="2026-10-06T09:00")
    a = make_task(client, title="A", start_at="2026-10-01T09:00", due_at="2026-10-02T09:00")
    assert [t["id"] for t in client.get("/api/tasks").json()] == [a["id"], b["id"]]


def test_filter_by_area(client):
    make_task(client, area="仕事")
    p = make_task(client, area="プライベート", related="")
    assert client.get("/api/tasks", params={"area": "プライベート"}).json() == [p]



def test_patch_updates_fields(client):
    t = make_task(client)
    r = client.patch(f"/api/tasks/{t['id']}", json={"done": True, "priority": "low"})
    assert r.status_code == 200
    body = r.json()
    assert body["done"] is True
    assert body["priority"] == "low"
    assert body["title"] == "資料作成"


def test_delete(client):
    t = make_task(client)
    assert client.delete(f"/api/tasks/{t['id']}").status_code == 204
    assert client.get("/api/tasks").json() == []


def test_missing_task_is_404(client):
    assert client.patch("/api/tasks/999", json={"done": True}).status_code == 404
    assert client.delete("/api/tasks/999").status_code == 404


def test_due_before_start_rejected(client):
    r = client.post("/api/tasks", json={
        "area": "仕事", "title": "x", "priority": "mid",
        "start_at": "2026-10-02T09:00", "due_at": "2026-10-01T09:00",
    })
    assert r.status_code == 422


def test_patch_due_before_existing_start_rejected(client):
    t = make_task(client)  # start 2026-09-28T09:00
    r = client.patch(f"/api/tasks/{t['id']}", json={"due_at": "2026-09-27T09:00"})
    assert r.status_code == 422
    assert client.get("/api/tasks").json()[0]["due_at"] == "2026-10-02T18:00"


@pytest.mark.parametrize("value", ["2026/10/01 09:00", "2026-10-01T09:00:00", "", "tomorrow"])
def test_invalid_datetime_rejected(client, value):
    r = client.post("/api/tasks", json={
        "area": "仕事", "title": "x", "priority": "mid",
        "start_at": value, "due_at": "2026-10-01T09:00",
    })
    assert r.status_code == 422


def test_invalid_priority_rejected(client):
    r = client.post("/api/tasks", json={
        "area": "仕事", "title": "x", "priority": "urgent",
        "start_at": "2026-10-01T09:00", "due_at": "2026-10-01T10:00",
    })
    assert r.status_code == 422


@pytest.mark.parametrize("field", ["area", "title"])
def test_blank_required_text_rejected(client, field):
    payload = {
        "area": "仕事", "title": "x", "priority": "mid",
        "start_at": "2026-10-01T09:00", "due_at": "2026-10-01T10:00",
    }
    payload[field] = "   "
    assert client.post("/api/tasks", json=payload).status_code == 422


def test_patch_null_for_required_field_rejected(client):
    t = make_task(client)
    assert client.patch(f"/api/tasks/{t['id']}", json={"title": None}).status_code == 422


def test_unknown_idea_id_rejected(client):
    r = client.post("/api/tasks", json={
        "area": "仕事", "title": "x", "priority": "mid",
        "start_at": "2026-10-01T09:00", "due_at": "2026-10-01T10:00", "idea_id": 999,
    })
    assert r.status_code == 422


def test_memo_defaults_to_empty_and_can_be_updated(client):
    t = make_task(client)
    assert t["memo"] == ""
    r = client.patch(f"/api/tasks/{t['id']}", json={"memo": "先方の要望:\n・図を多めに"})
    assert r.status_code == 200
    assert r.json()["memo"] == "先方の要望:\n・図を多めに"
    assert make_task(client, memo="初期メモ")["memo"] == "初期メモ"


def test_patch_null_memo_rejected(client):
    t = make_task(client)
    assert client.patch(f"/api/tasks/{t['id']}", json={"memo": None}).status_code == 422


def test_today_mark_set_and_clear(client):
    t = make_task(client)
    assert t["today_on"] is None
    r = client.patch(f"/api/tasks/{t['id']}", json={"today_on": "2026-09-28"})
    assert r.status_code == 200
    assert r.json()["today_on"] == "2026-09-28"
    r = client.patch(f"/api/tasks/{t['id']}", json={"today_on": None})
    assert r.json()["today_on"] is None


def test_today_mark_invalid_date_rejected(client):
    t = make_task(client)
    assert client.patch(f"/api/tasks/{t['id']}", json={"today_on": "9/28"}).status_code == 422


def test_links_default_empty_and_can_be_set(client):
    t = make_task(client)
    assert t["links"] == []
    links = [
        {"url": "https://example.com/spec", "label": "仕様書"},
        {"url": "http://intra.local/wiki"},
    ]
    r = client.patch(f"/api/tasks/{t['id']}", json={"links": links})
    assert r.status_code == 200
    assert r.json()["links"] == [
        {"url": "https://example.com/spec", "label": "仕様書"},
        {"url": "http://intra.local/wiki", "label": ""},
    ]
    assert client.get("/api/tasks").json()[0]["links"] == r.json()["links"]


def test_links_on_create_and_replace(client):
    t = make_task(client, links=[{"url": "https://a.example", "label": " A "}])
    assert t["links"] == [{"url": "https://a.example", "label": "A"}]
    r = client.patch(f"/api/tasks/{t['id']}", json={"links": []})
    assert r.json()["links"] == []


@pytest.mark.parametrize("url", [
    "javascript:alert(1)", "ftp://example.com", "example.com", "", "https://", "https://exa mple.com",
])
def test_unsafe_or_invalid_link_rejected(client, url):
    t = make_task(client)
    r = client.patch(f"/api/tasks/{t['id']}", json={"links": [{"url": url}]})
    assert r.status_code == 422


def test_link_url_is_stripped(client):
    t = make_task(client, links=[{"url": "  https://a.example/x  "}])
    assert t["links"][0]["url"] == "https://a.example/x"


def test_too_many_links_rejected(client):
    t = make_task(client)
    links = [{"url": f"https://example.com/{i}"} for i in range(21)]
    assert client.patch(f"/api/tasks/{t['id']}", json={"links": links}).status_code == 422


def test_patch_null_links_rejected(client):
    t = make_task(client)
    assert client.patch(f"/api/tasks/{t['id']}", json={"links": None}).status_code == 422
