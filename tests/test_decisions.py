import pytest


def make_decision(client, **overrides):
    payload = {"title": "経営会議", "date": "2026-10-15", "time": "10:00"}
    payload.update(overrides)
    r = client.post("/api/decisions", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_and_list(client):
    d = make_decision(client)
    assert d["title"] == "経営会議"
    assert d["date"] == "2026-10-15"
    assert d["time"] == "10:00"
    assert client.get("/api/decisions").json() == [d]


def test_time_is_optional(client):
    assert make_decision(client, time=None)["time"] is None
    assert make_decision(client, time="")["time"] is None
    r = client.post("/api/decisions", json={"title": "締切", "date": "2026-10-20"})
    assert r.status_code == 201
    assert r.json()["time"] is None


def test_list_is_ordered_by_date_then_time(client):
    c = make_decision(client, title="C", date="2026-10-16", time="09:00")
    b = make_decision(client, title="B", date="2026-10-15", time="15:00")
    a = make_decision(client, title="A", date="2026-10-15", time=None)
    assert [x["id"] for x in client.get("/api/decisions").json()] == [a["id"], b["id"], c["id"]]


@pytest.mark.parametrize("value", ["2026/10/15", "2026-02-30", "2026-10-15T10:00", "", "2026-1-5"])
def test_invalid_date_rejected(client, value):
    assert client.post("/api/decisions", json={"title": "x", "date": value}).status_code == 422


@pytest.mark.parametrize("value", ["25:00", "10:00:00", "9:00", "noon"])
def test_invalid_time_rejected(client, value):
    r = client.post("/api/decisions", json={"title": "x", "date": "2026-10-15", "time": value})
    assert r.status_code == 422


def test_blank_title_rejected(client):
    assert client.post("/api/decisions", json={"title": "  ", "date": "2026-10-15"}).status_code == 422


def test_patch_fields_and_clear_time(client):
    d = make_decision(client)
    r = client.patch(f"/api/decisions/{d['id']}", json={"title": "取締役会", "date": "2026-10-16"})
    assert r.status_code == 200
    assert r.json()["title"] == "取締役会"
    assert r.json()["date"] == "2026-10-16"
    assert r.json()["time"] == "10:00"
    r = client.patch(f"/api/decisions/{d['id']}", json={"time": None})
    assert r.json()["time"] is None


def test_patch_null_title_or_date_rejected(client):
    d = make_decision(client)
    assert client.patch(f"/api/decisions/{d['id']}", json={"title": None}).status_code == 422
    assert client.patch(f"/api/decisions/{d['id']}", json={"date": None}).status_code == 422


def test_delete(client):
    d = make_decision(client)
    assert client.delete(f"/api/decisions/{d['id']}").status_code == 204
    assert client.get("/api/decisions").json() == []


def test_missing_decision_is_404(client):
    assert client.patch("/api/decisions/999", json={"title": "x"}).status_code == 404
    assert client.delete("/api/decisions/999").status_code == 404
