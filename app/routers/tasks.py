import json
import sqlite3
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response

from app.db import get_conn, now_iso
from app.models import TaskCreate, TaskOut, TaskUpdate
from app.recurrence import generate
from app.routers.export import tasks_csv

router = APIRouter(prefix="/api", tags=["tasks"])

# PATCH で null を受け付けない列（idea_id だけは null で紐づけ解除できる）
NOT_NULL_FIELDS = {"area", "related", "title", "start_at", "due_at", "priority", "done", "memo", "links"}


def _task_from_row(row: sqlite3.Row) -> dict:
    task = dict(row)
    # リンクは [{url, label}, ...] を JSON 文字列で保存している
    task["links"] = json.loads(task["links"])
    return task


def _get_task(conn: sqlite3.Connection, task_id: int) -> dict:
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")
    return _task_from_row(row)


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


# 完了してからこの時間がたったタスクは TODO から外れ、アーカイブに表示される
ARCHIVE_AFTER = timedelta(days=2)
# アーカイブ（完了）したタスクは、完了から 1 年で自動的に削除する
RETENTION = timedelta(days=365)


def delete_expired_tasks(conn: sqlite3.Connection, now: datetime | None = None) -> None:
    limit = ((now or datetime.now()) - RETENTION).isoformat()
    conn.execute("DELETE FROM tasks WHERE done = 1 AND done_at IS NOT NULL AND done_at < ?", (limit,))
    conn.commit()


def _archive_limit() -> str:
    return (datetime.now() - ARCHIVE_AFTER).isoformat()


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(area: str | None = None, conn: sqlite3.Connection = Depends(get_conn)):
    delete_expired_tasks(conn)
    # 定期タスクの、まだ作っていない回をタスクにする
    generate(conn)
    # 完了して 2 日たったタスクはアーカイブに回すので、TODO には出さない
    where = "NOT (done = 1 AND done_at IS NOT NULL AND done_at < ?)"
    params: list = [_archive_limit()]
    if area:
        where += " AND area = ?"
        params.append(area)
    rows = conn.execute(f"SELECT * FROM tasks WHERE {where} ORDER BY start_at, id", params)
    return [_task_from_row(r) for r in rows]


PRIORITY_RANK = {"high": 0, "mid": 1, "low": 2}


@router.get("/tasks.csv")
def export_tasks(conn: sqlite3.Connection = Depends(get_conn)):
    """TODO に表示しているタスク（アーカイブに移ったものを除く）を CSV で。
    未完了 → 完了の順に、それぞれ期限の近い順 → 優先度 → 登録の古い順。"""
    tasks = sorted(
        list_tasks(conn=conn),
        key=lambda t: (t["done"], t["due_at"][:10], PRIORITY_RANK[t["priority"]], t["created_at"], t["id"]),
    )
    filename = f"tasks-{datetime.now():%Y%m%d}.csv"
    return Response(
        content=tasks_csv(tasks),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _archived_tasks(conn: sqlite3.Connection, q: str = "") -> list[dict]:
    delete_expired_tasks(conn)
    sql = "SELECT * FROM tasks WHERE done = 1 AND done_at IS NOT NULL AND done_at < ?"
    params: list = [_archive_limit()]
    if q:
        sql += " AND (title LIKE ? OR memo LIKE ? OR area LIKE ? OR related LIKE ?)"
        params += [f"%{q}%"] * 4
    rows = conn.execute(sql + " ORDER BY done_at DESC, id DESC", params)
    return [_task_from_row(r) for r in rows]


@router.get("/tasks/archived", response_model=list[TaskOut])
def list_archived_tasks(q: str = "", conn: sqlite3.Connection = Depends(get_conn)):
    """完了から 2 日以上たったタスク（完了の新しい順）。完了から 1 年を過ぎたものは削除する。"""
    return _archived_tasks(conn, q.strip())


@router.get("/tasks/archived.csv")
def export_archived_tasks(conn: sqlite3.Connection = Depends(get_conn)):
    filename = f"archived-tasks-{datetime.now():%Y%m%d}.csv"
    return Response(
        content=tasks_csv(_archived_tasks(conn)),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(body: TaskCreate, conn: sqlite3.Connection = Depends(get_conn)):
    _check_master(conn, body.area, body.related)
    _check_idea_exists(conn, body.idea_id)
    now = now_iso()
    cur = conn.execute(
        """INSERT INTO tasks (area, related, title, start_at, due_at, priority, done, idea_id, memo,
                              today_on, links, done_at, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (body.area, body.related, body.title, body.start_at, body.due_at, body.priority,
         int(body.done), body.idea_id, body.memo, body.today_on,
         json.dumps([link.model_dump() for link in body.links], ensure_ascii=False),
         now if body.done else None, now, now),
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
        # 完了にした日時を記録する（未完了に戻したら消す）。完了のまま保存し直しても日時は変えない
        if changes["done"] and not current["done"]:
            changes["done_at"] = now_iso()
        elif not changes["done"]:
            changes["done_at"] = None
        changes["done"] = int(changes["done"])
    if "links" in changes:
        changes["links"] = json.dumps(changes["links"], ensure_ascii=False)
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
