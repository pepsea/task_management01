import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response

from app.db import get_conn, now_iso
from app.models import BrainstormCreate, BrainstormOut, IdeaOut
from app.ordering import top_position
from app.routers.ideas import fetch_idea

router = APIRouter(prefix="/api", tags=["brainstorm"])


def _get_memo(conn: sqlite3.Connection, memo_id: int) -> dict:
    row = conn.execute("SELECT * FROM brainstorm WHERE id = ?", (memo_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="メモが見つかりません")
    return dict(row)


@router.get("/brainstorm", response_model=list[BrainstormOut])
def list_memos(conn: sqlite3.Connection = Depends(get_conn)):
    return [dict(r) for r in conn.execute("SELECT * FROM brainstorm ORDER BY created_at DESC, id DESC")]


@router.post("/brainstorm", response_model=BrainstormOut, status_code=201)
def add_memo(body: BrainstormCreate, conn: sqlite3.Connection = Depends(get_conn)):
    cur = conn.execute(
        "INSERT INTO brainstorm (text, created_at) VALUES (?, ?)", (body.text, now_iso())
    )
    conn.commit()
    return _get_memo(conn, cur.lastrowid)


@router.delete("/brainstorm/{memo_id}", status_code=204)
def delete_memo(memo_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    _get_memo(conn, memo_id)
    conn.execute("DELETE FROM brainstorm WHERE id = ?", (memo_id,))
    conn.commit()
    return Response(status_code=204)


@router.post("/brainstorm/{memo_id}/promote", response_model=IdeaOut, status_code=201)
def promote_memo(memo_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    memo = _get_memo(conn, memo_id)
    # アイディアの作成日時は、思いついた（メモした）日時を引き継ぐ
    cur = conn.execute(
        "INSERT INTO ideas (title, body, position, created_at, updated_at) VALUES (?, '', ?, ?, ?)",
        (memo["text"], top_position(conn, "ideas"), memo["created_at"], now_iso()),
    )
    conn.execute("DELETE FROM brainstorm WHERE id = ?", (memo_id,))
    conn.commit()
    return fetch_idea(conn, cur.lastrowid)
