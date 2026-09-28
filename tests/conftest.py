import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as c:
        yield c


def register(client, area, *related):
    """領域（と関連項目）をマスタに登録する。登録済みならそのまま使う。"""
    areas = {a["name"]: a for a in client.get("/api/areas").json()}
    if area in areas:
        area_obj = areas[area]
    else:
        r = client.post("/api/areas", json={"name": area})
        assert r.status_code == 201, r.text
        area_obj = r.json()
    existing = {x["name"] for x in area_obj["related"]}
    for name in related:
        if name not in existing:
            r = client.post(f"/api/areas/{area_obj['id']}/related", json={"name": name})
            assert r.status_code == 201, r.text
    return area_obj["id"]
