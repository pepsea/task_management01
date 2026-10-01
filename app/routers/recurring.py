import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response

from app.db import get_conn, now_iso
from app.models import RecurringIn, RecurringOut
from app.recurrence import generate, remove_upcoming
from app.routers.tasks import _check_master

router = APIRouter(prefix="/api", tags=["recurring"])

FIELDS = ("area", "related", "title", "priority", "memo", "rule", "day", "nth", "weekday", "lead_days", "start_from")


def _get(conn: sqlite3.Connection, recurring_id: int) -> dict:
    row = conn.execute("SELECT * FROM recurring_tasks WHERE id = ?", (recurring_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="定期タスクが見つかりません")
    return dict(row)


@router.get("/recurring", response_model=list[RecurringOut])
def list_recurring(conn: sqlite3.Connection = Depends(get_conn)):
    return [dict(r) for r in conn.execute("SELECT * FROM recurring_tasks ORDER BY id")]


@router.post("/recurring", response_model=RecurringOut, status_code=201)
def create_recurring(body: RecurringIn, conn: sqlite3.Connection = Depends(get_conn)):
    _check_master(conn, body.area, body.related)
    now = now_iso()
    values = body.model_dump()
    cur = conn.execute(
        f"""INSERT INTO recurring_tasks ({", ".join(FIELDS)}, created_at, updated_at)
            VALUES ({", ".join("?" for _ in FIELDS)}, ?, ?)""",
        (*(values[f] for f in FIELDS), now, now),
    )
    conn.commit()
    generate(conn)
    return _get(conn, cur.lastrowid)


@router.put("/recurring/{recurring_id}", response_model=RecurringOut)
def update_recurring(recurring_id: int, body: RecurringIn, conn: sqlite3.Connection = Depends(get_conn)):
    """内容を変えたら、これから先の未完了の回を作り直す（完了した回・期限の過ぎた回はそのまま）。"""
    _get(conn, recurring_id)
    _check_master(conn, body.area, body.related)
    values = body.model_dump()
    remove_upcoming(conn, recurring_id)
    conn.execute(
        f"""UPDATE recurring_tasks SET {", ".join(f"{f} = ?" for f in FIELDS)}, generated_until = NULL, updated_at = ?
            WHERE id = ?""",
        (*(values[f] for f in FIELDS), now_iso(), recurring_id),
    )
    conn.commit()
    generate(conn)
    return _get(conn, recurring_id)


@router.delete("/recurring/{recurring_id}", status_code=204)
def delete_recurring(recurring_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    """定期タスクを消し、これから先の未完了の回も消す（完了した回・期限の過ぎた回は普通のタスクとして残る）。"""
    _get(conn, recurring_id)
    remove_upcoming(conn, recurring_id)
    conn.execute("DELETE FROM recurring_tasks WHERE id = ?", (recurring_id,))
    conn.commit()
    return Response(status_code=204)
