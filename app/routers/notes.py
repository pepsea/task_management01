import re
import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response

from app.db import get_conn, now_iso
from app.markdown_render import render_markdown
from app.models import MarkdownIn, MarkdownOut, NoteCreate, NoteOut, NoteUpdate
from app.ordering import top_position
from app.routers.tags import set_item_tags, tags_by_item

router = APIRouter(prefix="/api", tags=["notes"])

TITLE_MAX = 100


def derive_title(body: str) -> str:
    """本文の最初の意味のある行から、Markdown の記号を除いてタイトルを作る。"""
    in_code = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not stripped:
            continue
        text = re.sub(r"^#{1,6}\s*", "", stripped)
        text = re.sub(r"^>\s*", "", text)
        text = re.sub(r"^([-*+]|\d+\.)\s+(\[[ xX]\]\s+)?", "", text)
        text = re.sub(r"[*_~`]", "", text).strip()
        if text:
            return text[:TITLE_MAX]
    return "無題"


def _like_pattern(q: str) -> str:
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _with_tags(conn: sqlite3.Connection, rows: list[dict]) -> list[dict]:
    tags = tags_by_item(conn, "note", [n["id"] for n in rows])
    for note in rows:
        note["tags"] = tags[note["id"]]
    return rows


def fetch_note(conn: sqlite3.Connection, note_id: int) -> dict:
    row = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="メモが見つかりません")
    return _with_tags(conn, [dict(row)])[0]


@router.post("/markdown", response_model=MarkdownOut)
def render_blocks(body: MarkdownIn):
    return {"html": [render_markdown(block) for block in body.blocks]}


@router.get("/notes", response_model=list[NoteOut])
def list_notes(
    q: str | None = None,
    tag: str | None = None,
    archived: bool = False,
    conn: sqlite3.Connection = Depends(get_conn),
):
    conditions = ["n.archived_at IS NOT NULL" if archived else "n.archived_at IS NULL"]
    params: list = []
    if q and q.strip():
        pattern = _like_pattern(q.strip())
        conditions.append("(n.title LIKE ? ESCAPE '\\' OR n.body LIKE ? ESCAPE '\\')")
        params += [pattern, pattern]
    if tag:
        conditions.append(
            "n.id IN (SELECT nt.note_id FROM note_tags nt JOIN tags g ON g.id = nt.tag_id WHERE g.name = ?)"
        )
        params.append(tag)
    # メモ帳は ★（ピン留め）を先頭に、その中はメモの日付の新しい順（同じ日付は後から作ったものが上）。
    # アーカイブはアーカイブの新しい順
    order = "n.archived_at DESC, n.id DESC" if archived else "n.pinned DESC, n.note_date DESC, n.id DESC"
    rows = conn.execute(f"SELECT n.* FROM notes n WHERE {' AND '.join(conditions)} ORDER BY {order}", params)
    return _with_tags(conn, [dict(r) for r in rows])


@router.post("/notes", response_model=NoteOut, status_code=201)
def create_note(body: NoteCreate, conn: sqlite3.Connection = Depends(get_conn)):
    now = now_iso()
    cur = conn.execute(
        """INSERT INTO notes (title, body, position, note_date, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (derive_title(body.body), body.body, top_position(conn, "notes"),
         body.note_date or date.today().isoformat(), now, now),
    )
    set_item_tags(conn, "note", cur.lastrowid, body.tags)
    conn.commit()
    return fetch_note(conn, cur.lastrowid)


@router.get("/notes/{note_id}", response_model=NoteOut)
def get_note(note_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    return fetch_note(conn, note_id)


@router.patch("/notes/{note_id}", response_model=NoteOut)
def update_note(note_id: int, body: NoteUpdate, conn: sqlite3.Connection = Depends(get_conn)):
    fetch_note(conn, note_id)
    changes = body.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise HTTPException(status_code=422, detail="body・tags・pinned・archived・note_date は null にできません")
    # ピン留め・アーカイブは内容の更新ではないので updated_at は変えない
    if "pinned" in changes:
        conn.execute("UPDATE notes SET pinned = ? WHERE id = ?", (int(changes["pinned"]), note_id))
    if "archived" in changes:
        archived_at = now_iso() if changes["archived"] else None
        conn.execute("UPDATE notes SET archived_at = ? WHERE id = ?", (archived_at, note_id))
    if "tags" in changes:
        set_item_tags(conn, "note", note_id, changes["tags"])
    if "note_date" in changes:
        conn.execute("UPDATE notes SET note_date = ? WHERE id = ?", (changes["note_date"], note_id))
    if "body" in changes or "tags" in changes or "note_date" in changes:
        conn.execute("UPDATE notes SET updated_at = ? WHERE id = ?", (now_iso(), note_id))
    if "body" in changes:
        conn.execute(
            "UPDATE notes SET body = ?, title = ? WHERE id = ?",
            (changes["body"], derive_title(changes["body"]), note_id),
        )
    conn.commit()
    return fetch_note(conn, note_id)


@router.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    fetch_note(conn, note_id)
    conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    return Response(status_code=204)
