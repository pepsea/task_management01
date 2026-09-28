"""アイディア・メモの手動の並び順（position 列）を扱う共通処理。"""

import sqlite3

from fastapi import HTTPException


def top_position(conn: sqlite3.Connection, table: str) -> int:
    """新しい項目を一覧の一番上に置くための並び順の値。"""
    return conn.execute(f"SELECT COALESCE(MIN(position), 0) - 1 FROM {table}").fetchone()[0]


def reorder(conn: sqlite3.Connection, table: str, ids: list[int], not_found: str) -> None:
    """ids（画面に表示されている順）が使っている並び順の値を、その順に割り当て直す。

    絞り込みで見えていない項目の位置は変わらない。
    """
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=422, detail="同じ項目が重複しています")
    placeholders = ",".join("?" * len(ids))
    found = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE id IN ({placeholders})", ids).fetchone()[0]
    if found != len(ids):
        raise HTTPException(status_code=404, detail=not_found)
    # 同じ値の並び順があると順番が決まらないので、まず全体を 0, 1, 2… に振り直す
    ordered = conn.execute(f"SELECT id FROM {table} ORDER BY position, id DESC").fetchall()
    for position, (item_id,) in enumerate(ordered):
        conn.execute(f"UPDATE {table} SET position = ? WHERE id = ?", (position, item_id))
    slots = sorted(r[0] for r in conn.execute(f"SELECT position FROM {table} WHERE id IN ({placeholders})", ids))
    for position, item_id in zip(slots, ids):
        conn.execute(f"UPDATE {table} SET position = ? WHERE id = ?", (position, item_id))
    conn.commit()
