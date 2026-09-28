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


def test_static_files_are_revalidated(client):
    # 画面の JS/CSS を更新したとき、古いキャッシュで画面が壊れないよう毎回確認させる
    for path in ["/", "/gantt.js", "/style.css"]:
        r = client.get(path)
        assert r.status_code == 200
        assert r.headers["cache-control"] == "no-cache"


def test_api_is_not_affected_by_static_cache_header(client):
    assert "no-cache" not in client.get("/api/health").headers.get("cache-control", "")
