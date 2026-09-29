import sqlite3
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response

from app.db import get_conn, now_iso
from app.markdown_render import render_markdown
from app.models import MarkdownIn, MarkdownOut, NoteCreate, NoteOut, NoteUpdate, ReorderIn
from app.ordering import reorder, top_position
from app.routers.tags import set_item_tags, tags_by_item

router = APIRouter(prefix="/api", tags=["notes"])

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
    sort: Literal["date", "manual"] = "date",
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
    # メモ帳は ★（ピン留め）を先頭に、その中は sort に応じて
    #   date: メモの日付の新しい順（同じ日付は後から作ったものが上）／ manual: ドラッグで決めた順。
    # アーカイブはアーカイブの新しい順
    if archived:
        order = "n.archived_at DESC, n.id DESC"
    elif sort == "manual":
        order = "n.pinned DESC, n.position, n.id DESC"
    else:
        order = "n.pinned DESC, n.note_date DESC, n.id DESC"
    rows = conn.execute(f"SELECT n.* FROM notes n WHERE {' AND '.join(conditions)} ORDER BY {order}", params)
    return _with_tags(conn, [dict(r) for r in rows])


@router.post("/notes", response_model=NoteOut, status_code=201)
def create_note(body: NoteCreate, conn: sqlite3.Connection = Depends(get_conn)):
    now = now_iso()
    cur = conn.execute(
        """INSERT INTO notes (title, body, position, note_date, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (body.title, body.body, top_position(conn, "notes"),
         body.note_date or date.today().isoformat(), now, now),
    )
    set_item_tags(conn, "note", cur.lastrowid, body.tags)
    conn.commit()
    return fetch_note(conn, cur.lastrowid)


@router.post("/notes/sort-by-date", status_code=204)
def sort_notes_by_date(conn: sqlite3.Connection = Depends(get_conn)):
    """手動の並び順を、メモの日付の新しい順（同じ日付は後から作ったものが上）に並べ直す。"""
    ids = [
        r[0]
        for r in conn.execute(
            "SELECT id FROM notes WHERE archived_at IS NULL ORDER BY note_date DESC, id DESC"
        )
    ]
    if ids:
        reorder(conn, "notes", ids, "メモが見つかりません")
    return Response(status_code=204)


@router.post("/notes/reorder", status_code=204)
def reorder_notes(body: ReorderIn, conn: sqlite3.Connection = Depends(get_conn)):
    reorder(conn, "notes", body.ids, "メモが見つかりません")
    return Response(status_code=204)


@router.get("/notes/{note_id}", response_model=NoteOut)
def get_note(note_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    return fetch_note(conn, note_id)


@router.patch("/notes/{note_id}", response_model=NoteOut)
def update_note(note_id: int, body: NoteUpdate, conn: sqlite3.Connection = Depends(get_conn)):
    fetch_note(conn, note_id)
    changes = body.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise HTTPException(
            status_code=422, detail="title・body・tags・pinned・archived・note_date は null にできません"
        )
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
    if "title" in changes:
        conn.execute("UPDATE notes SET title = ? WHERE id = ?", (changes["title"], note_id))
    if changes.keys() & {"title", "body", "tags", "note_date"}:
        conn.execute("UPDATE notes SET updated_at = ? WHERE id = ?", (now_iso(), note_id))
    if "body" in changes:
        conn.execute("UPDATE notes SET body = ? WHERE id = ?", (changes["body"], note_id))
    conn.commit()
    return fetch_note(conn, note_id)


@router.delete("/notes/{note_id}", status_code=204)
def delete_note(note_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    fetch_note(conn, note_id)
    conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    return Response(status_code=204)
