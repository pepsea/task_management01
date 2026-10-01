"""すべてのデータを ZIP でダウンロードする（ログイン情報は含めない）。"""

import csv
import io
import json
import re
import sqlite3
import zipfile
from datetime import datetime

from fastapi import APIRouter, Depends, Response

from app.db import get_conn
from app.markdown_portable import to_portable_markdown
from app.routers.tags import tags_by_item

router = APIRouter(prefix="/api", tags=["export"])

EXPORT_VERSION = 1
PRIORITY_LABEL = {"high": "高", "mid": "中", "low": "低"}

README = """Task & Idea Hub のエクスポート

data.json   すべてのデータ（タスク・ディシジョン・アイディア・ブレスト・メモ・領域・関連項目・タグ・リンク）
tasks.csv   タスクの一覧（Excel で開けます）
ideas.csv   アイディアの一覧（Excel で開けます）
notes/      メモ（Markdown）。アーカイブしたメモは notes/archive/

ログインのパスワードとログイン状態は含みません。
"""


def _rows(conn: sqlite3.Connection, sql: str) -> list[dict]:
    return [dict(r) for r in conn.execute(sql)]


def _with_tags(conn: sqlite3.Connection, kind: str, items: list[dict]) -> list[dict]:
    tags = tags_by_item(conn, kind, [i["id"] for i in items])
    for item in items:
        item["tags"] = tags[item["id"]]
    return items


def collect(conn: sqlite3.Connection) -> dict:
    tasks = _rows(conn, "SELECT * FROM tasks ORDER BY id")
    for task in tasks:
        task["done"] = bool(task["done"])
        task["links"] = json.loads(task["links"])
    ideas = _with_tags(conn, "idea", _rows(conn, "SELECT * FROM ideas ORDER BY id"))
    for idea in ideas:
        idea["prioritized"] = bool(idea["prioritized"])
    notes = _with_tags(conn, "note", _rows(conn, "SELECT * FROM notes ORDER BY id"))
    for note in notes:
        note["pinned"] = bool(note["pinned"])
    return {
        "format": "task-idea-hub-export",
        "version": EXPORT_VERSION,
        "exported_at": datetime.now().isoformat(timespec="seconds"),
        "tasks": tasks,
        "decisions": _rows(conn, "SELECT * FROM decisions ORDER BY date, id"),
        "ideas": ideas,
        "brainstorm": _rows(conn, "SELECT * FROM brainstorm ORDER BY id"),
        "notes": notes,
        "areas": _rows(conn, "SELECT * FROM areas ORDER BY id"),
        "related": _rows(conn, "SELECT * FROM related_items ORDER BY id"),
        "tags": _rows(conn, "SELECT * FROM tags ORDER BY id"),
        "links": _rows(conn, "SELECT id, title, target, position, created_at FROM quick_links ORDER BY position, id"),
    }


def _csv(header: list[str], rows: list[list]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    # Excel で文字化けしないよう BOM 付き UTF-8 にする
    return buffer.getvalue().encode("utf-8-sig")


def tasks_csv(tasks: list[dict]) -> bytes:
    """タスクの一覧を CSV にする（全データのエクスポートと、アーカイブのタスクの書き出しで共通）。"""
    return _csv(
        ["領域", "関連項目", "タスク名", "開始", "期限", "優先度", "完了", "完了日時", "今日のタスク", "メモ", "リンク"],
        [[t["area"], t["related"], t["title"], t["start_at"][:10], t["due_at"][:10], PRIORITY_LABEL[t["priority"]],
          "完了" if t["done"] else "", (t["done_at"] or "")[:16].replace("T", " "), t["today_on"] or "", t["memo"],
          "\n".join(link["url"] for link in t["links"])] for t in tasks],
    )


def _safe_filename(text: str) -> str:
    return re.sub(r'[\\/:*?"<>|\r\n\t]', "_", text)[:60]


def note_markdown(note: dict) -> str:
    """画面の「⬇ エクスポート」と同じ形: 「# タイトル」の下に本文（本文が同じ見出しで始まるなら本文のみ）。
    このアプリだけの書き方（蛍光ペン・文字色）は取り除く。"""
    title = note["title"] or "無題"
    body = to_portable_markdown(note["body"]).strip()
    first_line = body.split("\n", 1)[0].strip()
    return f"{body}\n" if first_line == f"# {title}" else f"# {title}\n\n{body}\n"


def build_zip(data: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.txt", README)
        z.writestr("data.json", json.dumps(data, ensure_ascii=False, indent=2))
        z.writestr("tasks.csv", tasks_csv(data["tasks"]))
        z.writestr("ideas.csv", _csv(
            ["タイトル", "本文", "タグ", "優先", "アーカイブ", "思いつき日時", "更新日時"],
            [[i["title"], i["body"], ", ".join(tag["name"] for tag in i["tags"]), "★" if i["prioritized"] else "",
              i["archived_at"] or "", i["created_at"], i["updated_at"]] for i in data["ideas"]],
        ))
        for note in data["notes"]:
            folder = "notes/archive" if note["archived_at"] else "notes"
            # ファイル名が重ならないように末尾にメモの番号を付ける
            name = f"{note['note_date']}_{_safe_filename(note['title'] or '無題')}_{note['id']}.md"
            z.writestr(f"{folder}/{name}", note_markdown(note))
    return buffer.getvalue()


@router.get("/export")
def export_all(conn: sqlite3.Connection = Depends(get_conn)):
    filename = f"task-idea-hub-export-{datetime.now():%Y%m%d-%H%M}.zip"
    return Response(
        content=build_zip(collect(conn)),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
