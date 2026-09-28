import csv
import io
import json
import zipfile

from tests.conftest import register


def export(client) -> zipfile.ZipFile:
    r = client.get("/api/export")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    disposition = r.headers["content-disposition"]
    assert disposition.startswith("attachment;") and ".zip" in disposition
    return zipfile.ZipFile(io.BytesIO(r.content))


def seed(client):
    register(client, "仕事", "PJ-A")
    client.post("/api/tasks", json={
        "area": "仕事", "related": "PJ-A", "title": "資料作成", "priority": "high",
        "start_at": "2026-10-01T09:00", "due_at": "2026-10-03T18:00", "memo": "図を多めに",
        "links": [{"url": "https://example.com", "label": "例"}],
    })
    client.post("/api/decisions", json={"title": "経営会議", "date": "2026-10-15"})
    idea = client.post("/api/ideas", json={"title": "新サービス", "body": "本文,カンマ", "tags": ["仕事"]}).json()
    client.patch(f"/api/ideas/{idea['id']}", json={"prioritized": True})
    client.post("/api/brainstorm", json={"text": "思いつき"})
    client.post("/api/notes", json={"title": "会議/メモ:1", "body": "- 議題", "note_date": "2026-10-01"})
    archived = client.post("/api/notes", json={"title": "古いメモ", "body": "# 古いメモ\n本文", "note_date": "2026-09-01"}).json()
    client.patch(f"/api/notes/{archived['id']}", json={"archived": True})
    client.post("/api/links", json={"title": "社内", "target": "C:\\share"})


def test_export_requires_login(anon_client):
    assert anon_client.get("/api/export").status_code == 401


def test_export_contains_all_data(client):
    seed(client)
    z = export(client)
    names = set(z.namelist())
    assert {"data.json", "tasks.csv", "ideas.csv", "README.txt"} <= names
    data = json.loads(z.read("data.json"))
    assert data["format"] == "task-idea-hub-export" and data["version"] == 1
    assert [t["title"] for t in data["tasks"]] == ["資料作成"]
    assert data["tasks"][0]["links"] == [{"url": "https://example.com", "label": "例"}]
    assert [d["title"] for d in data["decisions"]] == ["経営会議"]
    assert data["ideas"][0]["title"] == "新サービス"
    assert data["ideas"][0]["tags"][0]["name"] == "仕事"
    assert data["ideas"][0]["prioritized"] is True
    assert [b["text"] for b in data["brainstorm"]] == ["思いつき"]
    assert {n["title"] for n in data["notes"]} == {"会議/メモ:1", "古いメモ"}
    assert [a["name"] for a in data["areas"]] == ["仕事"]
    assert [r["name"] for r in data["related"]] == ["PJ-A"]
    assert [t["name"] for t in data["tags"]] == ["仕事"]
    assert [link["target"] for link in data["links"]] == ["C:\\share"]


def test_export_excludes_login_information(client):
    seed(client)
    z = export(client)
    raw = b"".join(z.read(name) for name in z.namelist())
    assert b"scrypt$" not in raw
    data = json.loads(z.read("data.json"))
    assert "users" not in data and "sessions" not in data


def test_notes_are_exported_as_markdown_files(client):
    seed(client)
    z = export(client)
    md = sorted(n for n in z.namelist() if n.endswith(".md"))
    assert len(md) == 2
    active = next(n for n in md if not n.startswith("notes/archive/"))
    archived = next(n for n in md if n.startswith("notes/archive/"))
    # ファイル名に使えない文字は _ に置き換える
    assert active.startswith("notes/2026-10-01_会議_メモ_1")
    assert z.read(active).decode() == "# 会議/メモ:1\n\n- 議題\n"
    # 本文が同じ見出しで始まるならタイトルを重ねない
    assert z.read(archived).decode() == "# 古いメモ\n本文\n"


def test_csv_files_open_in_excel(client):
    seed(client)
    z = export(client)
    raw = z.read("tasks.csv")
    assert raw.startswith(b"\xef\xbb\xbf")  # Excel で文字化けしないよう BOM 付き UTF-8
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    assert rows[0][:6] == ["領域", "関連項目", "タスク名", "開始", "期限", "優先度"]
    assert rows[1][:6] == ["仕事", "PJ-A", "資料作成", "2026-10-01T09:00", "2026-10-03T18:00", "高"]
    ideas = list(csv.reader(io.StringIO(z.read("ideas.csv").decode("utf-8-sig"))))
    assert ideas[1][0] == "新サービス" and ideas[1][1] == "本文,カンマ"


def test_export_of_empty_database(client):
    data = json.loads(export(client).read("data.json"))
    assert data["tasks"] == [] and data["notes"] == []
