import sqlite3


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_index_is_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Task &amp; Idea Hub" in r.text


def test_schema_is_created(client, tmp_path):
    conn = sqlite3.connect(tmp_path / "test.db")
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert {"tasks", "ideas", "brainstorm", "decisions"} <= names
