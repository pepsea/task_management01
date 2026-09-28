import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response

from app.db import get_conn
from app.models import AreaOut, MasterNameIn, RelatedOut

router = APIRouter(prefix="/api", tags=["masters"])


def _get_area(conn: sqlite3.Connection, area_id: int) -> dict:
    row = conn.execute("SELECT id, name FROM areas WHERE id = ?", (area_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="領域が見つかりません")
    return dict(row)


def _get_related(conn: sqlite3.Connection, related_id: int) -> dict:
    row = conn.execute(
        "SELECT id, area_id, name FROM related_items WHERE id = ?", (related_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="関連項目が見つかりません")
    return dict(row)


def _area_with_related(conn: sqlite3.Connection, area_id: int) -> dict:
    area = _get_area(conn, area_id)
    area["related"] = [
        dict(r)
        for r in conn.execute(
            "SELECT id, area_id, name FROM related_items WHERE area_id = ? ORDER BY id", (area_id,)
        )
    ]
    return area


@router.get("/areas", response_model=list[AreaOut])
def list_areas(conn: sqlite3.Connection = Depends(get_conn)):
    areas = [dict(r) for r in conn.execute("SELECT id, name FROM areas ORDER BY id")]
    related = {a["id"]: [] for a in areas}
    for r in conn.execute("SELECT id, area_id, name FROM related_items ORDER BY id"):
        related[r["area_id"]].append(dict(r))
    for area in areas:
        area["related"] = related[area["id"]]
    return areas


@router.post("/areas", response_model=AreaOut, status_code=201)
def create_area(body: MasterNameIn, conn: sqlite3.Connection = Depends(get_conn)):
    if conn.execute("SELECT 1 FROM areas WHERE name = ?", (body.name,)).fetchone():
        raise HTTPException(status_code=409, detail="同じ名前の領域がすでにあります")
    cur = conn.execute("INSERT INTO areas (name) VALUES (?)", (body.name,))
    conn.commit()
    return _area_with_related(conn, cur.lastrowid)


@router.patch("/areas/{area_id}", response_model=AreaOut)
def rename_area(area_id: int, body: MasterNameIn, conn: sqlite3.Connection = Depends(get_conn)):
    area = _get_area(conn, area_id)
    if conn.execute("SELECT 1 FROM areas WHERE name = ? AND id != ?", (body.name, area_id)).fetchone():
        raise HTTPException(status_code=409, detail="同じ名前の領域がすでにあります")
    conn.execute("UPDATE areas SET name = ? WHERE id = ?", (body.name, area_id))
    # タスクは領域を名前で持っているので、名前の変更をタスクにも反映する
    conn.execute("UPDATE tasks SET area = ? WHERE area = ?", (body.name, area["name"]))
    conn.commit()
    return _area_with_related(conn, area_id)


@router.delete("/areas/{area_id}", status_code=204)
def delete_area(area_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    area = _get_area(conn, area_id)
    used = conn.execute("SELECT COUNT(*) FROM tasks WHERE area = ?", (area["name"],)).fetchone()[0]
    if used:
        raise HTTPException(status_code=409, detail=f"この領域は {used} 件のタスクで使われているため削除できません")
    conn.execute("DELETE FROM areas WHERE id = ?", (area_id,))
    conn.commit()
    return Response(status_code=204)


@router.post("/areas/{area_id}/related", response_model=RelatedOut, status_code=201)
def create_related(area_id: int, body: MasterNameIn, conn: sqlite3.Connection = Depends(get_conn)):
    _get_area(conn, area_id)
    if conn.execute(
        "SELECT 1 FROM related_items WHERE area_id = ? AND name = ?", (area_id, body.name)
    ).fetchone():
        raise HTTPException(status_code=409, detail="この領域に同じ名前の関連項目がすでにあります")
    cur = conn.execute("INSERT INTO related_items (area_id, name) VALUES (?, ?)", (area_id, body.name))
    conn.commit()
    return _get_related(conn, cur.lastrowid)


@router.patch("/related/{related_id}", response_model=RelatedOut)
def rename_related(related_id: int, body: MasterNameIn, conn: sqlite3.Connection = Depends(get_conn)):
    related = _get_related(conn, related_id)
    if conn.execute(
        "SELECT 1 FROM related_items WHERE area_id = ? AND name = ? AND id != ?",
        (related["area_id"], body.name, related_id),
    ).fetchone():
        raise HTTPException(status_code=409, detail="この領域に同じ名前の関連項目がすでにあります")
    area = _get_area(conn, related["area_id"])
    conn.execute("UPDATE related_items SET name = ? WHERE id = ?", (body.name, related_id))
    conn.execute(
        "UPDATE tasks SET related = ? WHERE area = ? AND related = ?",
        (body.name, area["name"], related["name"]),
    )
    conn.commit()
    return _get_related(conn, related_id)


@router.delete("/related/{related_id}", status_code=204)
def delete_related(related_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    related = _get_related(conn, related_id)
    area = _get_area(conn, related["area_id"])
    used = conn.execute(
        "SELECT COUNT(*) FROM tasks WHERE area = ? AND related = ?", (area["name"], related["name"])
    ).fetchone()[0]
    if used:
        raise HTTPException(status_code=409, detail=f"この関連項目は {used} 件のタスクで使われているため削除できません")
    conn.execute("DELETE FROM related_items WHERE id = ?", (related_id,))
    conn.commit()
    return Response(status_code=204)
