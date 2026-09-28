import pytest
from fastapi.testclient import TestClient

from app.main import app


OWNER = {"username": "owner", "password": "correct-horse"}


@pytest.fixture
def anon_client(tmp_path, monkeypatch):
    """ログインしていない状態のクライアント（アカウントもまだ無い）。"""
    from app import auth

    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "test.db"))
    auth.reset_login_attempts()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client(anon_client):
    """初回設定を済ませてログインした状態のクライアント。"""
    r = anon_client.post("/api/auth/setup", json=OWNER)
    assert r.status_code == 201, r.text
    return anon_client



def register(client, area=None, *related):
    """領域・関連項目をマスタに登録する（両者は独立）。登録済みならそのまま使う。"""
    if area is not None:
        names = {a["name"] for a in client.get("/api/areas").json()}
        if area not in names:
            r = client.post("/api/areas", json={"name": area})
            assert r.status_code == 201, r.text
    existing = {x["name"] for x in client.get("/api/related").json()}
    for name in related:
        if name not in existing:
            r = client.post("/api/related", json={"name": name})
            assert r.status_code == 201, r.text
