import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response

from app.db import get_conn, now_iso
from app.models import DecisionCreate, DecisionOut, DecisionUpdate

router = APIRouter(prefix="/api", tags=["decisions"])


def _get_decision(conn: sqlite3.Connection, decision_id: int) -> dict:
    row = conn.execute("SELECT * FROM decisions WHERE id = ?", (decision_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="ディシジョンポイントが見つかりません")
    return dict(row)


@router.get("/decisions", response_model=list[DecisionOut])
def list_decisions(conn: sqlite3.Connection = Depends(get_conn)):
    # 時刻なし（NULL）は COALESCE で '' になり、同じ日の中で先頭に来る
    rows = conn.execute("SELECT * FROM decisions ORDER BY date, COALESCE(time, ''), id")
    return [dict(r) for r in rows]


@router.post("/decisions", response_model=DecisionOut, status_code=201)
def create_decision(body: DecisionCreate, conn: sqlite3.Connection = Depends(get_conn)):
    now = now_iso()
    cur = conn.execute(
        "INSERT INTO decisions (title, date, time, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (body.title, body.date, body.time, now, now),
    )
    conn.commit()
    return _get_decision(conn, cur.lastrowid)


@router.patch("/decisions/{decision_id}", response_model=DecisionOut)
def update_decision(decision_id: int, body: DecisionUpdate, conn: sqlite3.Connection = Depends(get_conn)):
    _get_decision(conn, decision_id)
    changes = body.model_dump(exclude_unset=True)
    for field in ("title", "date"):
        if field in changes and changes[field] is None:
            raise HTTPException(status_code=422, detail=f"{field} は空にできません")
    if changes:
        changes["updated_at"] = now_iso()
        assignments = ", ".join(f"{name} = ?" for name in changes)
        conn.execute(f"UPDATE decisions SET {assignments} WHERE id = ?", (*changes.values(), decision_id))
        conn.commit()
    return _get_decision(conn, decision_id)


@router.delete("/decisions/{decision_id}", status_code=204)
def delete_decision(decision_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    _get_decision(conn, decision_id)
    conn.execute("DELETE FROM decisions WHERE id = ?", (decision_id,))
    conn.commit()
    return Response(status_code=204)
