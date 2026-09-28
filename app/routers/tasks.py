import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response

from app.db import get_conn, now_iso
from app.models import TaskCreate, TaskOut, TaskUpdate

router = APIRouter(prefix="/api", tags=["tasks"])

# PATCH で null を受け付けない列（idea_id だけは null で紐づけ解除できる）
NOT_NULL_FIELDS = {"area", "related", "title", "start_at", "due_at", "priority", "done", "memo"}


def _get_task(conn: sqlite3.Connection, task_id: int) -> dict:
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")
    return dict(row)


def _check_idea_exists(conn: sqlite3.Connection, idea_id) -> None:
    if idea_id is None:
        return
    if conn.execute("SELECT 1 FROM ideas WHERE id = ?", (idea_id,)).fetchone() is None:
        raise HTTPException(status_code=422, detail="元アイディアが存在しません")


def _check_master(conn: sqlite3.Connection, area: str, related: str) -> None:
    if conn.execute("SELECT 1 FROM areas WHERE name = ?", (area,)).fetchone() is None:
        raise HTTPException(status_code=422, detail=f"領域「{area}」は登録されていません")
    if related and conn.execute("SELECT 1 FROM related_items WHERE name = ?", (related,)).fetchone() is None:
        raise HTTPException(status_code=422, detail=f"関連項目「{related}」は登録されていません")


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(area: str | None = None, conn: sqlite3.Connection = Depends(get_conn)):
    if area:
        rows = conn.execute("SELECT * FROM tasks WHERE area = ? ORDER BY start_at, id", (area,))
    else:
        rows = conn.execute("SELECT * FROM tasks ORDER BY start_at, id")
    return [dict(r) for r in rows]


@router.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(body: TaskCreate, conn: sqlite3.Connection = Depends(get_conn)):
    _check_master(conn, body.area, body.related)
    _check_idea_exists(conn, body.idea_id)
    now = now_iso()
    cur = conn.execute(
        """INSERT INTO tasks (area, related, title, start_at, due_at, priority, done, idea_id, memo,
                              today_on, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (body.area, body.related, body.title, body.start_at, body.due_at, body.priority,
         int(body.done), body.idea_id, body.memo, body.today_on, now, now),
    )
    conn.commit()
    return _get_task(conn, cur.lastrowid)


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, body: TaskUpdate, conn: sqlite3.Connection = Depends(get_conn)):
    current = _get_task(conn, task_id)
    changes = body.model_dump(exclude_unset=True)
    for field in NOT_NULL_FIELDS & changes.keys():
        if changes[field] is None:
            raise HTTPException(status_code=422, detail=f"{field} は空にできません")
    if "idea_id" in changes:
        _check_idea_exists(conn, changes["idea_id"])
    merged = {**current, **changes}
    if "area" in changes or "related" in changes:
        _check_master(conn, merged["area"], merged["related"])
    if merged["due_at"] < merged["start_at"]:
        raise HTTPException(status_code=422, detail="期限は開始日時以降にしてください")
    if not changes:
        return current
    if "done" in changes:
        changes["done"] = int(changes["done"])
    changes["updated_at"] = now_iso()
    # 列名は TaskUpdate のフィールド名に限られるので f-string で組み立てても安全
    assignments = ", ".join(f"{name} = ?" for name in changes)
    conn.execute(f"UPDATE tasks SET {assignments} WHERE id = ?", (*changes.values(), task_id))
    conn.commit()
    return _get_task(conn, task_id)


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    _get_task(conn, task_id)
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    return Response(status_code=204)
