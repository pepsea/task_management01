import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as c:
        yield c



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
