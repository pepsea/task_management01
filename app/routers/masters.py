import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response

from app.colors import next_color
from app.db import get_conn
from app.models import AreaOut, AreaUpdate, MasterNameIn, MasterOut

router = APIRouter(prefix="/api", tags=["masters"])

# 領域と関連項目は独立したマスタ。どちらも「表名・タスクの列名・画面での呼び名」だけが違う
MASTERS = {
    "areas": {"table": "areas", "task_column": "area", "label": "領域", "columns": "id, name, color"},
    "related": {"table": "related_items", "task_column": "related", "label": "関連項目", "columns": "id, name"},
}


def _get(conn: sqlite3.Connection, kind: str, item_id: int) -> dict:
    m = MASTERS[kind]
    row = conn.execute(f"SELECT {m['columns']} FROM {m['table']} WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"{m['label']}が見つかりません")
    return dict(row)


def _check_unique(conn: sqlite3.Connection, kind: str, name: str, exclude_id: int = -1) -> None:
    m = MASTERS[kind]
    if conn.execute(
        f"SELECT 1 FROM {m['table']} WHERE name = ? AND id != ?", (name, exclude_id)
    ).fetchone():
        raise HTTPException(status_code=409, detail=f"同じ名前の{m['label']}がすでにあります")


def _list(conn, kind):
    m = MASTERS[kind]
    return [dict(r) for r in conn.execute(f"SELECT {m['columns']} FROM {m['table']} ORDER BY id")]


def _create(conn, kind, name):
    _check_unique(conn, kind, name)
    if kind == "areas":
        cur = conn.execute("INSERT INTO areas (name, color) VALUES (?, ?)", (name, next_color(conn, "areas")))
    else:
        cur = conn.execute(f"INSERT INTO {MASTERS[kind]['table']} (name) VALUES (?)", (name,))
    conn.commit()
    return _get(conn, kind, cur.lastrowid)


def _rename(conn, kind, item_id, name):
    m = MASTERS[kind]
    current = _get(conn, kind, item_id)
    _check_unique(conn, kind, name, item_id)
    conn.execute(f"UPDATE {m['table']} SET name = ? WHERE id = ?", (name, item_id))
    # タスクは名前で持っているので、名前の変更をタスクにも反映する
    conn.execute(
        f"UPDATE tasks SET {m['task_column']} = ? WHERE {m['task_column']} = ?", (name, current["name"])
    )
    conn.commit()
    return _get(conn, kind, item_id)


def _delete(conn, kind, item_id):
    m = MASTERS[kind]
    current = _get(conn, kind, item_id)
    used = conn.execute(
        f"SELECT COUNT(*) FROM tasks WHERE {m['task_column']} = ?", (current["name"],)
    ).fetchone()[0]
    if used:
        raise HTTPException(
            status_code=409, detail=f"この{m['label']}は {used} 件のタスクで使われているため削除できません"
        )
    conn.execute(f"DELETE FROM {m['table']} WHERE id = ?", (item_id,))
    conn.commit()
    return Response(status_code=204)


@router.get("/areas", response_model=list[AreaOut])
def list_areas(conn: sqlite3.Connection = Depends(get_conn)):
    return _list(conn, "areas")


@router.post("/areas", response_model=AreaOut, status_code=201)
def create_area(body: MasterNameIn, conn: sqlite3.Connection = Depends(get_conn)):
    return _create(conn, "areas", body.name)


@router.patch("/areas/{item_id}", response_model=AreaOut)
def update_area(item_id: int, body: AreaUpdate, conn: sqlite3.Connection = Depends(get_conn)):
    changes = body.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise HTTPException(status_code=422, detail="name と color は空にできません")
    area = _get(conn, "areas", item_id)
    if "color" in changes:
        conn.execute("UPDATE areas SET color = ? WHERE id = ?", (changes["color"], item_id))
        conn.commit()
    if "name" in changes:
        return _rename(conn, "areas", item_id, changes["name"])
    return _get(conn, "areas", item_id) if changes else area


@router.delete("/areas/{item_id}", status_code=204)
def delete_area(item_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    return _delete(conn, "areas", item_id)


@router.get("/related", response_model=list[MasterOut])
def list_related(conn: sqlite3.Connection = Depends(get_conn)):
    return _list(conn, "related")


@router.post("/related", response_model=MasterOut, status_code=201)
def create_related(body: MasterNameIn, conn: sqlite3.Connection = Depends(get_conn)):
    return _create(conn, "related", body.name)


@router.patch("/related/{item_id}", response_model=MasterOut)
def rename_related(item_id: int, body: MasterNameIn, conn: sqlite3.Connection = Depends(get_conn)):
    return _rename(conn, "related", item_id, body.name)


@router.delete("/related/{item_id}", status_code=204)
def delete_related(item_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    return _delete(conn, "related", item_id)
