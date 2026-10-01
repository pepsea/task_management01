import sqlite3
from datetime import date, datetime, timedelta

import pytest

from app.db import db_path
from app.recurrence import LOOKAHEAD_DAYS, generate, occurrences
from tests.conftest import register


@pytest.fixture(autouse=True)
def masters(client):
    register(client, "仕事", "PJ-A")


def payload(**overrides):
    body = {"area": "仕事", "related": "PJ-A", "title": "月次報告", "priority": "high",
            "rule": "monthly_day", "day": 25, "start_from": date.today().isoformat()}
    body.update(overrides)
    return body


def recurring_tasks(client, recurring_id):
    return sorted((t for t in client.get("/api/tasks").json() if t["recurring_id"] == recurring_id),
                  key=lambda t: t["due_at"])


# --- 繰り返しの日の計算 ---

def test_monthly_day():
    rule = {"rule": "monthly_day", "day": 25}
    assert occurrences(rule, date(2026, 10, 1), date(2026, 12, 31)) == [
        date(2026, 10, 25), date(2026, 11, 25), date(2026, 12, 25)]


def test_monthly_day_31_falls_back_to_month_end():
    rule = {"rule": "monthly_day", "day": 31}
    assert occurrences(rule, date(2027, 1, 1), date(2027, 4, 30)) == [
        date(2027, 1, 31), date(2027, 2, 28), date(2027, 3, 31), date(2027, 4, 30)]


def test_monthly_nth_weekday():
    # 2026 年 10 月の第 2 火曜は 13 日、11 月は 10 日
    rule = {"rule": "monthly_weekday", "nth": 2, "weekday": 1}
    assert occurrences(rule, date(2026, 10, 1), date(2026, 11, 30)) == [date(2026, 10, 13), date(2026, 11, 10)]


def test_monthly_last_weekday():
    # 最終金曜: 2026/10/30、2026/11/27
    rule = {"rule": "monthly_weekday", "nth": 5, "weekday": 4}
    assert occurrences(rule, date(2026, 10, 1), date(2026, 11, 30)) == [date(2026, 10, 30), date(2026, 11, 27)]


def test_weekly():
    rule = {"rule": "weekly", "weekday": 0}  # 月曜
    assert occurrences(rule, date(2026, 10, 1), date(2026, 10, 20)) == [
        date(2026, 10, 5), date(2026, 10, 12), date(2026, 10, 19)]


def test_occurrences_respect_range_edges():
    rule = {"rule": "monthly_day", "day": 10}
    assert occurrences(rule, date(2026, 10, 10), date(2026, 11, 10)) == [date(2026, 10, 10), date(2026, 11, 10)]
    assert occurrences(rule, date(2026, 10, 11), date(2026, 11, 9)) == []


# --- API ---

def test_create_generates_upcoming_tasks(client):
    r = client.post("/api/recurring", json=payload(rule="weekly", weekday=date.today().weekday(), lead_days=2))
    assert r.status_code == 201, r.text
    rec = r.json()
    tasks = recurring_tasks(client, rec["id"])
    # 今日から LOOKAHEAD_DAYS 日先までの毎週（今日を含む）
    expected = occurrences(rec, date.today(), date.today() + timedelta(days=LOOKAHEAD_DAYS))
    assert [t["due_at"] for t in tasks] == [f"{d.isoformat()}T18:00" for d in expected]
    first = tasks[0]
    assert first["start_at"] == f"{(expected[0] - timedelta(days=2)).isoformat()}T09:00"
    assert (first["title"], first["area"], first["related"], first["priority"]) == ("月次報告", "仕事", "PJ-A", "high")


def test_generation_is_not_repeated(client):
    rec = client.post("/api/recurring", json=payload(rule="weekly", weekday=0)).json()
    count = len(recurring_tasks(client, rec["id"]))
    client.get("/api/tasks")
    assert len(recurring_tasks(client, rec["id"])) == count


def test_deleted_occurrence_is_not_recreated(client):
    rec = client.post("/api/recurring", json=payload(rule="weekly", weekday=0)).json()
    first = recurring_tasks(client, rec["id"])[0]
    client.delete(f"/api/tasks/{first['id']}")
    assert first["id"] not in [t["id"] for t in recurring_tasks(client, rec["id"])]


def test_later_days_generate_next_occurrences(client):
    rec = client.post("/api/recurring", json=payload(rule="monthly_day", day=1)).json()
    before = len(recurring_tasks(client, rec["id"]))
    with sqlite3.connect(db_path()) as conn:
        conn.row_factory = sqlite3.Row
        generate(conn, today=date.today() + timedelta(days=70))
    assert len(recurring_tasks(client, rec["id"])) > before


def test_past_occurrences_are_not_backfilled(client):
    old = (date.today() - timedelta(days=90)).isoformat()
    rec = client.post("/api/recurring", json=payload(rule="weekly", weekday=0, start_from=old)).json()
    assert all(t["due_at"][:10] >= date.today().isoformat() for t in recurring_tasks(client, rec["id"]))


def test_future_start_from(client):
    later = date.today() + timedelta(days=20)
    rec = client.post("/api/recurring", json=payload(rule="weekly", weekday=0, start_from=later.isoformat())).json()
    assert all(t["due_at"][:10] >= later.isoformat() for t in recurring_tasks(client, rec["id"]))


def test_update_regenerates_upcoming_but_keeps_done(client):
    rec = client.post("/api/recurring", json=payload(rule="weekly", weekday=0)).json()
    tasks = recurring_tasks(client, rec["id"])
    done = tasks[0]
    client.patch(f"/api/tasks/{done['id']}", json={"done": True})
    r = client.put(f"/api/recurring/{rec['id']}", json=payload(rule="weekly", weekday=0, title="週次報告"))
    assert r.status_code == 200, r.text
    after = recurring_tasks(client, rec["id"])
    assert done["id"] in [t["id"] for t in after]
    assert {t["title"] for t in after if t["id"] != done["id"]} == {"週次報告"}
    assert len([t for t in after if t["due_at"] == done["due_at"]]) == 1


def test_delete_removes_upcoming_open_tasks_only(client):
    rec = client.post("/api/recurring", json=payload(rule="weekly", weekday=0)).json()
    tasks = recurring_tasks(client, rec["id"])
    client.patch(f"/api/tasks/{tasks[0]['id']}", json={"done": True})
    assert client.delete(f"/api/recurring/{rec['id']}").status_code == 204
    remaining = client.get("/api/tasks").json()
    assert [t["id"] for t in remaining] == [tasks[0]["id"]]
    assert remaining[0]["recurring_id"] is None
    assert client.get("/api/recurring").json() == []


@pytest.mark.parametrize("body", [
    payload(rule="monthly_day", day=None),
    payload(rule="monthly_weekday", nth=2),
    payload(rule="weekly"),
    payload(day=32),
    payload(rule="monthly_weekday", nth=6, weekday=1),
    payload(start_from="2026/10/01"),
    payload(lead_days=61),
])
def test_invalid_rules_are_rejected(client, body):
    assert client.post("/api/recurring", json=body).status_code == 422


def test_unknown_area_is_rejected(client):
    assert client.post("/api/recurring", json=payload(area="未登録")).status_code == 422


def test_unused_fields_are_cleared(client):
    rec = client.post("/api/recurring", json=payload(rule="weekly", weekday=2, day=10, nth=3)).json()
    assert (rec["day"], rec["nth"], rec["weekday"]) == (None, None, 2)


def test_backup_restore_keeps_recurring(client):
    rec = client.post("/api/recurring", json=payload()).json()
    backup = client.post("/api/backups").json()
    client.delete(f"/api/recurring/{rec['id']}")
    assert client.post(f"/api/backups/{backup['name']}/restore").status_code == 200
    assert [r["id"] for r in client.get("/api/recurring").json()] == [rec["id"]]
