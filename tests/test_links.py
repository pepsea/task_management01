import pytest


def add(client, target, title=""):
    r = client.post("/api/links", json={"title": title, "target": target})
    assert r.status_code == 201, r.text
    return r.json()


def test_add_and_list_new_on_top(client):
    a = add(client, "https://example.com", "例")
    b = add(client, "https://intra.example.com/wiki")
    assert a["kind"] == "web" and a["title"] == "例"
    assert [x["id"] for x in client.get("/api/links").json()] == [b["id"], a["id"]]


@pytest.mark.parametrize("target,kind", [
    ("https://example.com/a?b=1", "web"),
    ("http://intra/wiki", "web"),
    ("C:\\share\\資料", "path"),
    ("C://xxx/yyy", "path"),
    ("d:/data", "path"),
    ("\\\\fileserver\\共有\\営業", "path"),
    ("//fileserver/share", "path"),
    ("file:///Users/me/doc.pdf", "path"),
    ("smb://fileserver/share", "smb"),
])
def test_kinds(client, target, kind):
    assert add(client, target)["kind"] == kind


@pytest.mark.parametrize("target", [
    "javascript:alert(1)", "data:text/html,x", "ftp://example.com", "example.com", "", "   ", "https://",
])
def test_invalid_targets_rejected(client, target):
    assert client.post("/api/links", json={"target": target}).status_code == 422


def test_target_is_stripped(client):
    assert add(client, "  https://example.com  ")["target"] == "https://example.com"


def test_update_and_delete(client):
    a = add(client, "https://example.com", "例")
    r = client.patch(f"/api/links/{a['id']}", json={"title": "新", "target": "C:\\work"})
    assert r.status_code == 200
    assert r.json()["title"] == "新" and r.json()["kind"] == "path"
    assert client.patch(f"/api/links/{a['id']}", json={"target": "javascript:x"}).status_code == 422
    assert client.patch(f"/api/links/{a['id']}", json={"target": None}).status_code == 422
    assert client.delete(f"/api/links/{a['id']}").status_code == 204
    assert client.get("/api/links").json() == []


def test_reorder(client):
    a, b, c = add(client, "https://a.example"), add(client, "https://b.example"), add(client, "https://c.example")
    assert client.post("/api/links/reorder", json={"ids": [a["id"], b["id"], c["id"]]}).status_code == 204
    assert [x["id"] for x in client.get("/api/links").json()] == [a["id"], b["id"], c["id"]]


def test_missing_link_is_404(client):
    assert client.patch("/api/links/999", json={"title": "x"}).status_code == 404
    assert client.delete("/api/links/999").status_code == 404
