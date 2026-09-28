import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response

from app.colors import next_color
from app.db import get_conn
from app.models import TagOut, TagUpdate

router = APIRouter(prefix="/api", tags=["tags"])

def _get_tag(conn: sqlite3.Connection, tag_id: int) -> dict:
    row = conn.execute("SELECT id, name, color FROM tags WHERE id = ?", (tag_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="タグが見つかりません")
    return dict(row)


def get_or_create_tag(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
    if row is not None:
        return row[0]
    cur = conn.execute("INSERT INTO tags (name, color) VALUES (?, ?)", (name, next_color(conn, "tags")))
    return cur.lastrowid


def set_idea_tags(conn: sqlite3.Connection, idea_id: int, names: list[str]) -> None:
    unique_names = list(dict.fromkeys(names))
    conn.execute("DELETE FROM idea_tags WHERE idea_id = ?", (idea_id,))
    for position, name in enumerate(unique_names):
        conn.execute(
            "INSERT INTO idea_tags (idea_id, tag_id, position) VALUES (?, ?, ?)",
            (idea_id, get_or_create_tag(conn, name), position),
        )


def tags_by_idea(conn: sqlite3.Connection, idea_ids: list[int]) -> dict[int, list[dict]]:
    result: dict[int, list[dict]] = {idea_id: [] for idea_id in idea_ids}
    if not idea_ids:
        return result
    placeholders = ",".join("?" * len(idea_ids))
    rows = conn.execute(
        f"""SELECT it.idea_id, g.id, g.name, g.color FROM idea_tags it
            JOIN tags g ON g.id = it.tag_id
            WHERE it.idea_id IN ({placeholders})
            ORDER BY it.idea_id, it.position""",
        idea_ids,
    )
    for idea_id, tag_id, name, color in rows:
        result[idea_id].append({"id": tag_id, "name": name, "color": color})
    return result


@router.get("/tags", response_model=list[TagOut])
def list_tags(conn: sqlite3.Connection = Depends(get_conn)):
    return [dict(r) for r in conn.execute("SELECT id, name, color FROM tags ORDER BY name")]


@router.patch("/tags/{tag_id}", response_model=TagOut)
def update_tag(tag_id: int, body: TagUpdate, conn: sqlite3.Connection = Depends(get_conn)):
    _get_tag(conn, tag_id)
    changes = body.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise HTTPException(status_code=422, detail="name と color は空にできません")
    if "name" in changes:
        clash = conn.execute(
            "SELECT 1 FROM tags WHERE name = ? AND id != ?", (changes["name"], tag_id)
        ).fetchone()
        if clash:
            raise HTTPException(status_code=409, detail="同じ名前のタグがすでにあります")
    if changes:
        assignments = ", ".join(f"{name} = ?" for name in changes)
        conn.execute(f"UPDATE tags SET {assignments} WHERE id = ?", (*changes.values(), tag_id))
        conn.commit()
    return _get_tag(conn, tag_id)


@router.delete("/tags/{tag_id}", status_code=204)
def delete_tag(tag_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    _get_tag(conn, tag_id)
    conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
    conn.commit()
    return Response(status_code=204)
