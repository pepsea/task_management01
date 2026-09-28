import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response

from app.db import get_conn, now_iso
from app.models import IdeaCreate, IdeaOut, IdeaUpdate
from app.routers.tags import set_idea_tags, tags_by_idea

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
    idea = dict(row)
    idea["tags"] = tags_by_idea(conn, [idea_id])[idea_id]
    return idea


@router.get("/ideas", response_model=list[IdeaOut])
def list_ideas(q: str | None = None, tag: str | None = None, conn: sqlite3.Connection = Depends(get_conn)):
    conditions, params = [], []
    if q and q.strip():
        pattern = _like_pattern(q.strip())
        conditions.append("(i.title LIKE ? ESCAPE '\\' OR i.body LIKE ? ESCAPE '\\')")
        params += [pattern, pattern]
    if tag:
        conditions.append(
            "i.id IN (SELECT it.idea_id FROM idea_tags it JOIN tags g ON g.id = it.tag_id WHERE g.name = ?)"
        )
        params.append(tag)
    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    ideas = [dict(r) for r in conn.execute(SELECT_IDEAS + where + " ORDER BY i.updated_at DESC, i.id DESC", params)]
    tags = tags_by_idea(conn, [i["id"] for i in ideas])
    for idea in ideas:
        idea["tags"] = tags[idea["id"]]
    return ideas


@router.post("/ideas", response_model=IdeaOut, status_code=201)
def create_idea(body: IdeaCreate, conn: sqlite3.Connection = Depends(get_conn)):
    now = now_iso()
    cur = conn.execute(
        "INSERT INTO ideas (title, body, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (body.title, body.body, now, now),
    )
    set_idea_tags(conn, cur.lastrowid, body.tags)
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
        raise HTTPException(status_code=422, detail="title・body・tags は null にできません")
    tags = changes.pop("tags", None)
    if tags is not None:
        set_idea_tags(conn, idea_id, tags)
    if changes or tags is not None:
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
