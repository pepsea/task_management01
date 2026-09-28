import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response

from app.db import get_conn, now_iso
from app.models import IdeaCreate, IdeaOut, IdeaUpdate

router = APIRouter(prefix="/api", tags=["ideas"])

SELECT_IDEAS = """
SELECT i.*, (SELECT COUNT(*) FROM tasks t WHERE t.idea_id = i.id) AS task_count
FROM ideas i
"""


def _like_pattern(q: str) -> str:
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def fetch_idea(conn: sqlite3.Connection, idea_id: int) -> dict:
    row = conn.execute(SELECT_IDEAS + " WHERE i.id = ?", (idea_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="アイディアが見つかりません")
    return dict(row)


@router.get("/ideas", response_model=list[IdeaOut])
def list_ideas(q: str | None = None, conn: sqlite3.Connection = Depends(get_conn)):
    order = " ORDER BY i.updated_at DESC, i.id DESC"
    if q and q.strip():
        pattern = _like_pattern(q.strip())
        rows = conn.execute(
            SELECT_IDEAS + " WHERE i.title LIKE ? ESCAPE '\\' OR i.body LIKE ? ESCAPE '\\'" + order,
            (pattern, pattern),
        )
    else:
        rows = conn.execute(SELECT_IDEAS + order)
    return [dict(r) for r in rows]


@router.post("/ideas", response_model=IdeaOut, status_code=201)
def create_idea(body: IdeaCreate, conn: sqlite3.Connection = Depends(get_conn)):
    now = now_iso()
    cur = conn.execute(
        "INSERT INTO ideas (title, body, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (body.title, body.body, now, now),
    )
    conn.commit()
    return fetch_idea(conn, cur.lastrowid)


@router.get("/ideas/{idea_id}", response_model=IdeaOut)
def get_idea(idea_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    return fetch_idea(conn, idea_id)


@router.patch("/ideas/{idea_id}", response_model=IdeaOut)
def update_idea(idea_id: int, body: IdeaUpdate, conn: sqlite3.Connection = Depends(get_conn)):
    fetch_idea(conn, idea_id)
    changes = body.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise HTTPException(status_code=422, detail="title と body は空にできません")
    if changes:
        changes["updated_at"] = now_iso()
        assignments = ", ".join(f"{name} = ?" for name in changes)
        conn.execute(f"UPDATE ideas SET {assignments} WHERE id = ?", (*changes.values(), idea_id))
        conn.commit()
    return fetch_idea(conn, idea_id)


@router.delete("/ideas/{idea_id}", status_code=204)
def delete_idea(idea_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    fetch_idea(conn, idea_id)
    # 外部キー ON DELETE SET NULL により、紐づくタスクの idea_id は NULL になる
    conn.execute("DELETE FROM ideas WHERE id = ?", (idea_id,))
    conn.commit()
    return Response(status_code=204)
