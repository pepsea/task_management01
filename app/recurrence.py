"""定期タスクの繰り返しの日を求め、回ごとのタスクを作る。"""

import calendar
import sqlite3
from datetime import date, datetime, timedelta

from app.db import now_iso

# 今日からこの日数先までの回を、前もってタスクとして作っておく
LOOKAHEAD_DAYS = 31


def _month_starts(start: date, end: date):
    year, month = start.year, start.month
    while date(year, month, 1) <= end:
        yield year, month
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


def _nth_weekday(year: int, month: int, nth: int, weekday: int) -> date:
    """その月の第 nth weekday 曜日（nth=5 は最終）。"""
    days_in_month = calendar.monthrange(year, month)[1]
    if nth == 5:
        last = date(year, month, days_in_month)
        return last - timedelta(days=(last.weekday() - weekday) % 7)
    first = date(year, month, 1)
    day = first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (nth - 1))
    # 第 4 までなら必ずその月の中に収まる
    return day


def occurrences(rule: dict, start: date, end: date) -> list[date]:
    """start〜end（両端を含む）にある繰り返しの日。"""
    days: list[date] = []
    if rule["rule"] == "weekly":
        first = start + timedelta(days=(rule["weekday"] - start.weekday()) % 7)
        day = first
        while day <= end:
            days.append(day)
            day += timedelta(days=7)
        return days
    for year, month in _month_starts(start, end):
        if rule["rule"] == "monthly_day":
            # 31 日などその月に無い日は月末にする
            day = date(year, month, min(rule["day"], calendar.monthrange(year, month)[1]))
        else:
            day = _nth_weekday(year, month, rule["nth"], rule["weekday"])
        if start <= day <= end:
            days.append(day)
    return days


def business_days_before(day: date, count: int) -> date:
    """day から土日を除いて count 日さかのぼった日。"""
    while count > 0:
        day -= timedelta(days=1)
        if day.weekday() < 5:
            count -= 1
    return day


def generate(conn: sqlite3.Connection, today: date | None = None) -> None:
    """定期タスクごとに、まだ作っていない回（今日から LOOKAHEAD_DAYS 日先まで）をタスクとして作る。
    初めて作るときは、開始日と今日の遅い方からにする（過去の回をさかのぼって作らない）。"""
    today = today or datetime.now().date()
    end = today + timedelta(days=LOOKAHEAD_DAYS)
    now = now_iso()
    for row in conn.execute("SELECT * FROM recurring_tasks").fetchall():
        rule = dict(row)
        start_from = date.fromisoformat(rule["start_from"])
        if rule["generated_until"] is None:
            begin = max(start_from, today)
        else:
            begin = max(start_from, date.fromisoformat(rule["generated_until"]) + timedelta(days=1))
        if begin > end:
            continue
        # 同じ日の回がもうある（完了して残した回など）ときは作らない
        existing = {r[0] for r in conn.execute(
            "SELECT substr(due_at, 1, 10) FROM tasks WHERE recurring_id = ?", (rule["id"],))}
        for due in occurrences(rule, begin, end):
            if due.isoformat() in existing:
                continue
            # 開始は期限から土日を除いて lead_days 日前
            start = business_days_before(due, rule["lead_days"])
            conn.execute(
                """INSERT INTO tasks (area, related, title, start_at, due_at, priority, done, memo, links,
                                      recurring_id, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, 0, ?, '[]', ?, ?, ?)""",
                (rule["area"], rule["related"], rule["title"], f"{start.isoformat()}T09:00",
                 f"{due.isoformat()}T18:00", rule["priority"], rule["memo"], rule["id"], now, now),
            )
        conn.execute("UPDATE recurring_tasks SET generated_until = ? WHERE id = ?", (end.isoformat(), rule["id"]))
    conn.commit()


def remove_upcoming(conn: sqlite3.Connection, recurring_id: int, today: date | None = None) -> None:
    """その定期タスクから作った、期限が今日以降の未完了の回を消す（変更・削除のとき）。"""
    today = today or datetime.now().date()
    conn.execute(
        "DELETE FROM tasks WHERE recurring_id = ? AND done = 0 AND due_at >= ?",
        (recurring_id, today.isoformat()),
    )
