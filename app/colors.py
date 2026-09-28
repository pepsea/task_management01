import sqlite3

# タグと領域に自動で割り当てる色。使われている数が少ない色から順に使う
PALETTE = ["#2563eb", "#16a34a", "#dc2626", "#d97706", "#7c3aed", "#db2777", "#0891b2", "#4b5563"]


def next_color(conn: sqlite3.Connection, table: str) -> str:
    usage = {color: 0 for color in PALETTE}
    for (color,) in conn.execute(f"SELECT color FROM {table} WHERE color IS NOT NULL"):
        if color in usage:
            usage[color] += 1
    return min(PALETTE, key=lambda c: usage[c])
