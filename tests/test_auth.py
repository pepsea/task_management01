import sqlite3

import pytest

from tests.conftest import OWNER


def test_status_before_setup(anon_client):
    assert anon_client.get("/api/auth/status").json() == {"needs_setup": True, "logged_in": False, "username": None}


def test_pages_redirect_to_setup_before_account_exists(anon_client):
    r = anon_client.get("/", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/setup.html"


def test_api_requires_login(anon_client):
    assert anon_client.get("/api/tasks").status_code == 401
    assert anon_client.post("/api/brainstorm", json={"text": "x"}).status_code == 401


@pytest.mark.parametrize("path", ["/setup.html", "/login.html", "/auth.js", "/style.css", "/api/health", "/api/auth/status"])
def test_public_paths(anon_client, path):
    assert anon_client.get(path, follow_redirects=False).status_code == 200


def test_setup_creates_account_and_logs_in(anon_client):
    r = anon_client.post("/api/auth/setup", json=OWNER)
    assert r.status_code == 201
    assert r.json() == {"username": "owner"}
    set_cookie = r.headers["set-cookie"].lower()
    assert "httponly" in set_cookie and "samesite=lax" in set_cookie and "max-age=2592000" in set_cookie
    assert anon_client.get("/api/tasks").status_code == 200
    assert anon_client.get("/api/auth/me").json() == {"username": "owner"}


def test_setup_only_once(client):
    assert client.post("/api/auth/setup", json={"username": "x", "password": "another-pass"}).status_code == 409


@pytest.mark.parametrize("payload", [
    {"username": "owner", "password": "short"},
    {"username": "  ", "password": "long-enough"},
])
def test_setup_validation(anon_client, payload):
    assert anon_client.post("/api/auth/setup", json=payload).status_code == 422


def test_pages_redirect_to_login_after_logout(client):
    assert client.post("/api/auth/logout").status_code == 204
    r = client.get("/notes.html", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/login.html"
    assert client.get("/api/tasks").status_code == 401


def test_login(client):
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={**OWNER, "password": "wrong-pass"}).status_code == 401
    assert client.post("/api/auth/login", json={**OWNER, "username": "other"}).status_code == 401
    assert client.get("/api/tasks").status_code == 401
    r = client.post("/api/auth/login", json=OWNER)
    assert r.status_code == 200
    assert client.get("/api/tasks").status_code == 200


def test_login_is_locked_after_repeated_failures(client):
    client.post("/api/auth/logout")
    for _ in range(5):
        assert client.post("/api/auth/login", json={**OWNER, "password": "wrong-pass"}).status_code == 401
    # 正しいパスワードでもロック中は入れない
    assert client.post("/api/auth/login", json=OWNER).status_code == 429


def test_expired_session_is_rejected(client, tmp_path):
    conn = sqlite3.connect(tmp_path / "test.db")
    conn.execute("UPDATE sessions SET expires_at = '2000-01-01T00:00:00'")
    conn.commit()
    conn.close()
    assert client.get("/api/tasks").status_code == 401


def test_session_is_extended_when_used(client, tmp_path):
    conn = sqlite3.connect(tmp_path / "test.db")
    conn.execute("UPDATE sessions SET expires_at = '2099-01-01T00:00:00', renewed_at = '2000-01-01T00:00:00'")
    conn.commit()
    assert client.get("/api/tasks").status_code == 200
    renewed = conn.execute("SELECT renewed_at, expires_at FROM sessions").fetchone()
    conn.close()
    assert renewed[0] > "2000-01-01"
    assert renewed[1] < "2099-01-01"  # 使った時点から 30 日後に更新される


def test_password_is_not_stored_in_plain_text(client, tmp_path):
    conn = sqlite3.connect(tmp_path / "test.db")
    stored = conn.execute("SELECT password_hash FROM users").fetchone()[0]
    token = conn.execute("SELECT token_hash FROM sessions").fetchone()[0]
    conn.close()
    assert OWNER["password"] not in stored
    assert stored.startswith("scrypt$")
    assert token not in client.cookies.get("session", "")


def test_change_password(client, anon_client):
    assert client.post("/api/auth/password", json={"current": "wrong-pass", "new": "new-password"}).status_code == 400
    assert client.post("/api/auth/password", json={"current": OWNER["password"], "new": "short"}).status_code == 422
    assert client.post("/api/auth/password", json={"current": OWNER["password"], "new": "new-password"}).status_code == 204
    # 変更したブラウザはログインしたまま
    assert client.get("/api/tasks").status_code == 200
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json=OWNER).status_code == 401
    assert client.post("/api/auth/login", json={**OWNER, "password": "new-password"}).status_code == 200


def test_change_password_logs_out_other_browsers(client, tmp_path):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as other:
        assert other.post("/api/auth/login", json=OWNER).status_code == 200
        client.post("/api/auth/password", json={"current": OWNER["password"], "new": "new-password"})
        assert other.get("/api/tasks").status_code == 401
        assert client.get("/api/tasks").status_code == 200


def test_cli_reset_password(client):
    from app.cli import reset_password

    reset_password("reset-password-1")
    # 再設定するとすべてのログインが解除される
    assert client.get("/api/tasks").status_code == 401
    assert client.post("/api/auth/login", json={**OWNER, "password": "reset-password-1"}).status_code == 200


def test_cli_reset_password_rejects_short_password(client):
    from app.cli import reset_password

    with pytest.raises(ValueError):
        reset_password("short")
