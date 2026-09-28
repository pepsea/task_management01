import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response

from app.db import get_conn, now_iso
from app.models import LinkCreate, LinkOut, LinkUpdate, ReorderIn, link_kind
from app.ordering import reorder, top_position

router = APIRouter(prefix="/api", tags=["links"])


def _link_from_row(row: sqlite3.Row) -> dict:
    link = dict(row)
    link["kind"] = link_kind(link["target"])
    return link


def _get_link(conn: sqlite3.Connection, link_id: int) -> dict:
    row = conn.execute("SELECT * FROM quick_links WHERE id = ?", (link_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="リンクが見つかりません")
    return _link_from_row(row)


@router.get("/links", response_model=list[LinkOut])
def list_links(conn: sqlite3.Connection = Depends(get_conn)):
    return [_link_from_row(r) for r in conn.execute("SELECT * FROM quick_links ORDER BY position, id DESC")]


@router.post("/links", response_model=LinkOut, status_code=201)
def create_link(body: LinkCreate, conn: sqlite3.Connection = Depends(get_conn)):
    cur = conn.execute(
        "INSERT INTO quick_links (title, target, position, created_at) VALUES (?, ?, ?, ?)",
        (body.title, body.target, top_position(conn, "quick_links"), now_iso()),
    )
    conn.commit()
    return _get_link(conn, cur.lastrowid)


@router.post("/links/reorder", status_code=204)
def reorder_links(body: ReorderIn, conn: sqlite3.Connection = Depends(get_conn)):
    reorder(conn, "quick_links", body.ids, "リンクが見つかりません")
    return Response(status_code=204)


@router.patch("/links/{link_id}", response_model=LinkOut)
def update_link(link_id: int, body: LinkUpdate, conn: sqlite3.Connection = Depends(get_conn)):
    _get_link(conn, link_id)
    changes = body.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise HTTPException(status_code=422, detail="title と target は null にできません")
    if changes:
        assignments = ", ".join(f"{name} = ?" for name in changes)
        conn.execute(f"UPDATE quick_links SET {assignments} WHERE id = ?", (*changes.values(), link_id))
        conn.commit()
    return _get_link(conn, link_id)


@router.delete("/links/{link_id}", status_code=204)
def delete_link(link_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    _get_link(conn, link_id)
    conn.execute("DELETE FROM quick_links WHERE id = ?", (link_id,))
    conn.commit()
    return Response(status_code=204)
