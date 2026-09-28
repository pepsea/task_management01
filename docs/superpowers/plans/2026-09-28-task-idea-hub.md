# タスク＆アイディアハブ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 左2/3にTODOガントチャート、右1/3にアイディア保管庫とブレストメモを並べた、個人用のローカルWebアプリを `http://localhost:5003` で動かす。

**Architecture:** FastAPI が JSON API（`/api/...`）と静的フロントエンド（`static/`）を同じポート 5003 で配信する。データは SQLite ファイル 1 つ（`data/app.db`）に保存する。フロントはビルド不要の素の ES Modules で、パネルごとにファイルを分け、`main.js` がパネル間の連携（タスク化・昇格）をつなぐ。

**Tech Stack:** Python 3.10+ / FastAPI / Uvicorn / sqlite3（標準ライブラリ）/ Pydantic v2 / pytest + TestClient（httpx）/ HTML + CSS + JavaScript（ES Modules）

**Spec:** `docs/superpowers/specs/2026-09-28-task-idea-hub-design.md`

## Global Constraints

- ポートは `5003` 固定（`uvicorn app.main:app --port 5003`）
- DB ファイルのパスは既定で `data/app.db`。環境変数 `APP_DB_PATH` があればそちらを使う
- 日時の形式は `YYYY-MM-DDTHH:MM`（`<input type="datetime-local">` の値と同じ）。それ以外は 422 にする
- 優先度は `high` / `mid` / `low` の3値のみ。画面表示は 高 / 中 / 低、色は 高＝赤、中＝橙、低＝灰
- 期限 `due_at` は開始日時 `start_at` 以上であること
- 認証なし、単一ユーザー
- 外部 CDN や JS ライブラリは使わない（素の HTML/CSS/JS のみ）
- ユーザーが入力した文字列は `textContent` で DOM に入れる（`innerHTML` に入れない）
- 画面の文言は日本語
- コミットメッセージの末尾に `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` を付ける

## Review Focus

1. **部分更新で期限だけを開始日時より前に変える** → 既存の値とマージしたうえで判定して 422 を返し、DB は変わらないこと（Task 2 で `test_patch_due_before_existing_start_rejected` を追加）
2. **空白だけのタイトル・領域・ブレストメモ**（`"   "`）→ 前後の空白を除いて空なら 422 を返すこと（Task 2・3・4 の `*_blank_*` テストで確認）
3. **タスク化済みのアイディアを削除する** → タスクは残り、`idea_id` が `null` になること（Task 3 で `test_delete_idea_keeps_tasks` を追加）
4. **検索語に `%` や `_` を含む**（例：「100%」）→ ワイルドカードとして扱わず、文字どおりに検索すること（Task 3 で `test_search_escapes_like_wildcards` を追加）
5. **日時の形式が違う**（`2026/10/01`、秒付き、空文字など）→ 422 を返し、500 にならないこと（Task 2 で `test_invalid_datetime_rejected` を追加）

フロントで手動確認する項目（Task 9）：日本語入力の変換確定の Enter でブレストメモが追加されないこと、表示期間をはみ出すタスクのバーが切り取られて表示されること。

---

## ファイル構成

| ファイル | 役割 |
|---|---|
| `requirements.txt` | 依存パッケージ |
| `run.sh` | 5003 番ポートで起動 |
| `app/__init__.py`, `app/routers/__init__.py` | パッケージ化（空ファイル） |
| `app/db.py` | DB パスの決定、接続、スキーマ初期化、`get_conn` 依存関数、`now_iso` |
| `app/models.py` | Pydantic の入力・出力モデル |
| `app/main.py` | アプリ生成、lifespan で DB 初期化、ルーター登録、静的ファイル配信 |
| `app/routers/tasks.py` | `/api/tasks`, `/api/areas` |
| `app/routers/ideas.py` | `/api/ideas` と `fetch_idea` |
| `app/routers/brainstorm.py` | `/api/brainstorm` と昇格 |
| `static/index.html` | 画面の骨組み、タスク用ダイアログ |
| `static/style.css` | 全体のスタイル |
| `static/ui.js` | `el()`（DOM 生成）、`toast()` |
| `static/dates.js` | 日付の計算・表示用の関数 |
| `static/api.js` | fetch ラッパーと API 関数 |
| `static/gantt.js` | ガントの描画と表示期間の管理 |
| `static/taskForm.js` | タスクの作成・編集ダイアログ |
| `static/ideas.js` | 保管庫パネル |
| `static/brainstorm.js` | ブレストパネル |
| `static/main.js` | 初期化とパネル間の連携 |
| `tests/conftest.py` | 一時 DB を使う `client` フィクスチャ |
| `tests/test_app.py`, `tests/test_tasks.py`, `tests/test_ideas.py`, `tests/test_brainstorm.py` | API テスト |

---

### Task 1: プロジェクト骨組み・DB 初期化・静的配信

**Files:**
- Create: `requirements.txt`, `run.sh`, `app/__init__.py`, `app/routers/__init__.py`, `app/db.py`, `app/main.py`, `static/index.html`, `tests/__init__.py`, `tests/conftest.py`
- Test: `tests/test_app.py`

**Interfaces:**
- Produces:
  - `app.db.connect() -> sqlite3.Connection`（`row_factory=sqlite3.Row`、外部キー有効）
  - `app.db.init_db() -> None`
  - `app.db.get_conn()`（FastAPI の依存関数。接続を yield して最後に close する。**commit は各ハンドラーで明示的に行う**）
  - `app.db.now_iso() -> str`（マイクロ秒付きのローカル時刻 ISO 文字列）
  - `app.main.app`（FastAPI インスタンス）
  - `tests/conftest.py` の `client` フィクスチャ（テストごとに一時 DB を使う TestClient）

- [ ] **Step 1: Python のバージョンを確認し、仮想環境と依存パッケージを用意する**

Run: `python3 --version`
Expected: `Python 3.10` 以上。3.9 以下なら作業を止めて報告する。

`requirements.txt`:
```
fastapi>=0.110
uvicorn[standard]>=0.29
pytest>=8.0
httpx>=0.27
```

Run: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
Expected: `Successfully installed ...`

- [ ] **Step 2: 失敗するテストを書く**

`tests/__init__.py`: 空ファイル

`tests/conftest.py`:
```python
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as c:
        yield c
```

`tests/test_app.py`:
```python
import sqlite3


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_index_is_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Task &amp; Idea Hub" in r.text


def test_schema_is_created(client, tmp_path):
    conn = sqlite3.connect(tmp_path / "test.db")
    names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    assert {"tasks", "ideas", "brainstorm"} <= names
```

- [ ] **Step 3: テストが失敗することを確認する**

Run: `.venv/bin/pytest tests/test_app.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app'`）

- [ ] **Step 4: 実装する**

`app/__init__.py`、`app/routers/__init__.py`: 空ファイル

`app/db.py`:
```python
import os
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS ideas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    body TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    area TEXT NOT NULL,
    related TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    start_at TEXT NOT NULL,
    due_at TEXT NOT NULL,
    priority TEXT NOT NULL CHECK (priority IN ('high', 'mid', 'low')),
    done INTEGER NOT NULL DEFAULT 0,
    idea_id INTEGER REFERENCES ideas(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS brainstorm (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def db_path() -> Path:
    return Path(os.environ.get("APP_DB_PATH", DEFAULT_DB_PATH))


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # FastAPI は同期の依存関数とハンドラーを別スレッドで動かすことがあるため
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with closing(connect()) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def get_conn():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def now_iso() -> str:
    return datetime.now().isoformat()
```

`app/main.py`:
```python
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import init_db

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Task & Idea Hub", lifespan=lifespan)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# API ルーターはこの行より上で登録する（"/" のマウントは全パスに一致するため最後に置く）
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
```

`static/index.html`（Task 5 で置き換える仮の画面）:
```html
<!doctype html>
<html lang="ja">
<head><meta charset="utf-8"><title>Task &amp; Idea Hub</title></head>
<body><h1>Task &amp; Idea Hub</h1></body>
</html>
```

`run.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 5003 "$@"
```

Run: `chmod +x run.sh`

- [ ] **Step 5: テストが通ることを確認する**

Run: `.venv/bin/pytest tests/test_app.py -v`
Expected: 3 passed

- [ ] **Step 6: コミットする**

```bash
git add requirements.txt run.sh app static tests
git commit -m "feat: FastAPI の骨組みと SQLite の初期化を追加

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: タスク API

**Files:**
- Create: `app/models.py`, `app/routers/tasks.py`
- Modify: `app/main.py`（ルーター登録）
- Test: `tests/test_tasks.py`

**Interfaces:**
- Consumes: `get_conn`, `now_iso`（Task 1）
- Produces:
  - `app.models.NonEmptyStr`, `Priority`, `TaskCreate`, `TaskUpdate`, `TaskOut`
  - `GET /api/tasks?area=` → `TaskOut[]`（`start_at`, `id` の昇順）
  - `POST /api/tasks` → 201 `TaskOut`
  - `PATCH /api/tasks/{id}` → `TaskOut`
  - `DELETE /api/tasks/{id}` → 204
  - `GET /api/areas` → `string[]`（重複なし、昇順）
  - `TaskOut` の JSON: `{id, area, related, title, start_at, due_at, priority, done(bool), idea_id(int|null), created_at, updated_at}`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_tasks.py`:
```python
import pytest


def make_task(client, **overrides):
    payload = {
        "area": "仕事",
        "related": "PJ-A",
        "title": "資料作成",
        "start_at": "2026-09-28T09:00",
        "due_at": "2026-10-02T18:00",
        "priority": "high",
    }
    payload.update(overrides)
    r = client.post("/api/tasks", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def test_create_and_list(client):
    t = make_task(client)
    assert t["id"] > 0
    assert t["done"] is False
    assert t["idea_id"] is None
    assert client.get("/api/tasks").json() == [t]


def test_list_is_ordered_by_start(client):
    b = make_task(client, title="B", start_at="2026-10-05T09:00", due_at="2026-10-06T09:00")
    a = make_task(client, title="A", start_at="2026-10-01T09:00", due_at="2026-10-02T09:00")
    assert [t["id"] for t in client.get("/api/tasks").json()] == [a["id"], b["id"]]


def test_filter_by_area(client):
    make_task(client, area="仕事")
    p = make_task(client, area="プライベート")
    assert client.get("/api/tasks", params={"area": "プライベート"}).json() == [p]


def test_areas_are_distinct_and_sorted(client):
    make_task(client, area="b")
    make_task(client, area="a")
    make_task(client, area="b")
    assert client.get("/api/areas").json() == ["a", "b"]


def test_patch_updates_fields(client):
    t = make_task(client)
    r = client.patch(f"/api/tasks/{t['id']}", json={"done": True, "priority": "low"})
    assert r.status_code == 200
    body = r.json()
    assert body["done"] is True
    assert body["priority"] == "low"
    assert body["title"] == "資料作成"


def test_delete(client):
    t = make_task(client)
    assert client.delete(f"/api/tasks/{t['id']}").status_code == 204
    assert client.get("/api/tasks").json() == []


def test_missing_task_is_404(client):
    assert client.patch("/api/tasks/999", json={"done": True}).status_code == 404
    assert client.delete("/api/tasks/999").status_code == 404


def test_due_before_start_rejected(client):
    r = client.post("/api/tasks", json={
        "area": "仕事", "title": "x", "priority": "mid",
        "start_at": "2026-10-02T09:00", "due_at": "2026-10-01T09:00",
    })
    assert r.status_code == 422


def test_patch_due_before_existing_start_rejected(client):
    t = make_task(client)  # start 2026-09-28T09:00
    r = client.patch(f"/api/tasks/{t['id']}", json={"due_at": "2026-09-27T09:00"})
    assert r.status_code == 422
    assert client.get("/api/tasks").json()[0]["due_at"] == "2026-10-02T18:00"


@pytest.mark.parametrize("value", ["2026/10/01 09:00", "2026-10-01T09:00:00", "", "tomorrow"])
def test_invalid_datetime_rejected(client, value):
    r = client.post("/api/tasks", json={
        "area": "仕事", "title": "x", "priority": "mid",
        "start_at": value, "due_at": "2026-10-01T09:00",
    })
    assert r.status_code == 422


def test_invalid_priority_rejected(client):
    r = client.post("/api/tasks", json={
        "area": "仕事", "title": "x", "priority": "urgent",
        "start_at": "2026-10-01T09:00", "due_at": "2026-10-01T10:00",
    })
    assert r.status_code == 422


@pytest.mark.parametrize("field", ["area", "title"])
def test_blank_required_text_rejected(client, field):
    payload = {
        "area": "仕事", "title": "x", "priority": "mid",
        "start_at": "2026-10-01T09:00", "due_at": "2026-10-01T10:00",
    }
    payload[field] = "   "
    assert client.post("/api/tasks", json=payload).status_code == 422


def test_patch_null_for_required_field_rejected(client):
    t = make_task(client)
    assert client.patch(f"/api/tasks/{t['id']}", json={"title": None}).status_code == 422


def test_unknown_idea_id_rejected(client):
    r = client.post("/api/tasks", json={
        "area": "仕事", "title": "x", "priority": "mid",
        "start_at": "2026-10-01T09:00", "due_at": "2026-10-01T10:00", "idea_id": 999,
    })
    assert r.status_code == 422
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `.venv/bin/pytest tests/test_tasks.py -v`
Expected: FAIL（`/api/tasks` が静的ファイル側に渡り 404/405 になる）

- [ ] **Step 3: モデルを実装する**

`app/models.py`:
```python
from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, StringConstraints, field_validator, model_validator

DT_FORMAT = "%Y-%m-%dT%H:%M"

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Priority = Literal["high", "mid", "low"]


def check_datetime(value: Optional[str]) -> Optional[str]:
    if value is None:
        return value
    # strptime は形式が違えば ValueError を出し、Pydantic が 422 に変換する
    datetime.strptime(value, DT_FORMAT)
    if len(value) != 16:
        raise ValueError("日時は YYYY-MM-DDTHH:MM 形式で指定してください")
    return value


class TaskCreate(BaseModel):
    area: NonEmptyStr
    related: Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)] = ""
    title: NonEmptyStr
    start_at: str
    due_at: str
    priority: Priority
    done: bool = False
    idea_id: Optional[int] = None

    @field_validator("start_at", "due_at")
    @classmethod
    def validate_datetimes(cls, value):
        return check_datetime(value)

    @model_validator(mode="after")
    def due_not_before_start(self):
        if self.due_at < self.start_at:
            raise ValueError("期限は開始日時以降にしてください")
        return self


class TaskUpdate(BaseModel):
    area: Optional[NonEmptyStr] = None
    related: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]] = None
    title: Optional[NonEmptyStr] = None
    start_at: Optional[str] = None
    due_at: Optional[str] = None
    priority: Optional[Priority] = None
    done: Optional[bool] = None
    idea_id: Optional[int] = None

    @field_validator("start_at", "due_at")
    @classmethod
    def validate_datetimes(cls, value):
        return check_datetime(value)


class TaskOut(BaseModel):
    id: int
    area: str
    related: str
    title: str
    start_at: str
    due_at: str
    priority: Priority
    done: bool
    idea_id: Optional[int]
    created_at: str
    updated_at: str
```

- [ ] **Step 4: ルーターを実装する**

`app/routers/tasks.py`:
```python
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response

from app.db import get_conn, now_iso
from app.models import TaskCreate, TaskOut, TaskUpdate

router = APIRouter(prefix="/api", tags=["tasks"])

# PATCH で null を受け付けない列（idea_id だけは null で紐づけ解除できる）
NOT_NULL_FIELDS = {"area", "related", "title", "start_at", "due_at", "priority", "done"}


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


@router.get("/tasks", response_model=list[TaskOut])
def list_tasks(area: str | None = None, conn: sqlite3.Connection = Depends(get_conn)):
    if area:
        rows = conn.execute("SELECT * FROM tasks WHERE area = ? ORDER BY start_at, id", (area,))
    else:
        rows = conn.execute("SELECT * FROM tasks ORDER BY start_at, id")
    return [dict(r) for r in rows]


@router.get("/areas", response_model=list[str])
def list_areas(conn: sqlite3.Connection = Depends(get_conn)):
    return [r[0] for r in conn.execute("SELECT DISTINCT area FROM tasks ORDER BY area")]


@router.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(body: TaskCreate, conn: sqlite3.Connection = Depends(get_conn)):
    _check_idea_exists(conn, body.idea_id)
    now = now_iso()
    cur = conn.execute(
        """INSERT INTO tasks (area, related, title, start_at, due_at, priority, done, idea_id,
                              created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (body.area, body.related, body.title, body.start_at, body.due_at, body.priority,
         int(body.done), body.idea_id, now, now),
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
```

`app/main.py` を変更する。`from app.db import init_db` の下に import を追加し、`app.mount(...)` の直前にルーター登録を追加する:
```python
from app.routers import tasks
```
```python
app.include_router(tasks.router)
```

- [ ] **Step 5: テストが通ることを確認する**

Run: `.venv/bin/pytest -v`
Expected: all passed（test_app 3件＋test_tasks 全件）

- [ ] **Step 6: コミットする**

```bash
git add app tests
git commit -m "feat: タスクの CRUD API と領域一覧 API を追加

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: アイディア API

**Files:**
- Modify: `app/models.py`（アイディア用モデルを追加）, `app/main.py`（ルーター登録）
- Create: `app/routers/ideas.py`
- Test: `tests/test_ideas.py`

**Interfaces:**
- Consumes: `get_conn`, `now_iso`（Task 1）、`NonEmptyStr`（Task 2）、`POST /api/tasks` の `idea_id`（Task 2）
- Produces:
  - `app.models.IdeaCreate`, `IdeaUpdate`, `IdeaOut`
  - `app.routers.ideas.fetch_idea(conn, idea_id: int) -> dict`（`task_count` を含む。無ければ 404）
  - `GET /api/ideas?q=` → `IdeaOut[]`（`updated_at` 降順、同時刻は `id` 降順）
  - `POST /api/ideas` → 201 `IdeaOut`
  - `GET /api/ideas/{id}` / `PATCH /api/ideas/{id}` → `IdeaOut`
  - `DELETE /api/ideas/{id}` → 204
  - `IdeaOut` の JSON: `{id, title, body, created_at, updated_at, task_count}`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_ideas.py`:
```python
def make_idea(client, title="アイディアA", body=""):
    r = client.post("/api/ideas", json={"title": title, "body": body})
    assert r.status_code == 201, r.text
    return r.json()


def test_create_get_and_list(client):
    i = make_idea(client, body="本文")
    assert i["task_count"] == 0
    assert client.get(f"/api/ideas/{i['id']}").json() == i
    assert client.get("/api/ideas").json() == [i]


def test_list_is_newest_updated_first(client):
    a = make_idea(client, "A")
    b = make_idea(client, "B")
    assert [x["id"] for x in client.get("/api/ideas").json()] == [b["id"], a["id"]]
    client.patch(f"/api/ideas/{a['id']}", json={"body": "更新"})
    assert [x["id"] for x in client.get("/api/ideas").json()] == [a["id"], b["id"]]


def test_patch(client):
    i = make_idea(client)
    r = client.patch(f"/api/ideas/{i['id']}", json={"title": "新タイトル"})
    assert r.status_code == 200
    assert r.json()["title"] == "新タイトル"
    assert r.json()["body"] == ""


def test_search_title_and_body(client):
    make_idea(client, "旅行計画", "北海道")
    make_idea(client, "読書メモ", "旅行記を読む")
    make_idea(client, "家計", "")
    titles = {x["title"] for x in client.get("/api/ideas", params={"q": "旅行"}).json()}
    assert titles == {"旅行計画", "読書メモ"}


def test_search_escapes_like_wildcards(client):
    make_idea(client, "達成率100%")
    make_idea(client, "達成率1000")
    make_idea(client, "a_b")
    make_idea(client, "axb")
    assert [x["title"] for x in client.get("/api/ideas", params={"q": "100%"}).json()] == ["達成率100%"]
    assert [x["title"] for x in client.get("/api/ideas", params={"q": "a_b"}).json()] == ["a_b"]


def test_task_count(client):
    i = make_idea(client)
    client.post("/api/tasks", json={
        "area": "仕事", "title": i["title"], "priority": "mid",
        "start_at": "2026-10-01T09:00", "due_at": "2026-10-08T18:00", "idea_id": i["id"],
    })
    assert client.get(f"/api/ideas/{i['id']}").json()["task_count"] == 1
    assert client.get("/api/ideas").json()[0]["task_count"] == 1


def test_delete_idea_keeps_tasks(client):
    i = make_idea(client)
    t = client.post("/api/tasks", json={
        "area": "仕事", "title": "x", "priority": "mid",
        "start_at": "2026-10-01T09:00", "due_at": "2026-10-08T18:00", "idea_id": i["id"],
    }).json()
    assert client.delete(f"/api/ideas/{i['id']}").status_code == 204
    tasks = client.get("/api/tasks").json()
    assert [x["id"] for x in tasks] == [t["id"]]
    assert tasks[0]["idea_id"] is None


def test_missing_idea_is_404(client):
    assert client.get("/api/ideas/999").status_code == 404
    assert client.patch("/api/ideas/999", json={"title": "x"}).status_code == 404
    assert client.delete("/api/ideas/999").status_code == 404


def test_blank_title_rejected(client):
    assert client.post("/api/ideas", json={"title": "  "}).status_code == 422
    i = make_idea(client)
    assert client.patch(f"/api/ideas/{i['id']}", json={"title": " "}).status_code == 422
    assert client.patch(f"/api/ideas/{i['id']}", json={"title": None}).status_code == 422
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `.venv/bin/pytest tests/test_ideas.py -v`
Expected: FAIL（`/api/ideas` が 404/405）

- [ ] **Step 3: モデルを追加する**

`app/models.py` の末尾に追加:
```python
class IdeaCreate(BaseModel):
    title: NonEmptyStr
    body: str = ""


class IdeaUpdate(BaseModel):
    title: Optional[NonEmptyStr] = None
    body: Optional[str] = None


class IdeaOut(BaseModel):
    id: int
    title: str
    body: str
    created_at: str
    updated_at: str
    task_count: int
```

- [ ] **Step 4: ルーターを実装する**

`app/routers/ideas.py`:
```python
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response

from app.db import get_conn, now_iso
from app.models import IdeaCreate, IdeaOut, IdeaUpdate

router = APIRouter(prefix="/api", tags=["ideas"])

SELECT_IDEAS = """
SELECT i.*, (SELECT COUNT(*) FROM tasks t WHERE t.idea_id = i.id) AS task_count
FROM ideas i
"""


def _like_pattern(q: str) -> str:
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def fetch_idea(conn: sqlite3.Connection, idea_id: int) -> dict:
    row = conn.execute(SELECT_IDEAS + " WHERE i.id = ?", (idea_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="アイディアが見つかりません")
    return dict(row)


@router.get("/ideas", response_model=list[IdeaOut])
def list_ideas(q: str | None = None, conn: sqlite3.Connection = Depends(get_conn)):
    order = " ORDER BY i.updated_at DESC, i.id DESC"
    if q and q.strip():
        pattern = _like_pattern(q.strip())
        rows = conn.execute(
            SELECT_IDEAS + " WHERE i.title LIKE ? ESCAPE '\\' OR i.body LIKE ? ESCAPE '\\'" + order,
            (pattern, pattern),
        )
    else:
        rows = conn.execute(SELECT_IDEAS + order)
    return [dict(r) for r in rows]


@router.post("/ideas", response_model=IdeaOut, status_code=201)
def create_idea(body: IdeaCreate, conn: sqlite3.Connection = Depends(get_conn)):
    now = now_iso()
    cur = conn.execute(
        "INSERT INTO ideas (title, body, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (body.title, body.body, now, now),
    )
    conn.commit()
    return fetch_idea(conn, cur.lastrowid)


@router.get("/ideas/{idea_id}", response_model=IdeaOut)
def get_idea(idea_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    return fetch_idea(conn, idea_id)


@router.patch("/ideas/{idea_id}", response_model=IdeaOut)
def update_idea(idea_id: int, body: IdeaUpdate, conn: sqlite3.Connection = Depends(get_conn)):
    fetch_idea(conn, idea_id)
    changes = body.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise HTTPException(status_code=422, detail="title と body は空にできません")
    if changes:
        changes["updated_at"] = now_iso()
        assignments = ", ".join(f"{name} = ?" for name in changes)
        conn.execute(f"UPDATE ideas SET {assignments} WHERE id = ?", (*changes.values(), idea_id))
        conn.commit()
    return fetch_idea(conn, idea_id)


@router.delete("/ideas/{idea_id}", status_code=204)
def delete_idea(idea_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    fetch_idea(conn, idea_id)
    # 外部キー ON DELETE SET NULL により、紐づくタスクの idea_id は NULL になる
    conn.execute("DELETE FROM ideas WHERE id = ?", (idea_id,))
    conn.commit()
    return Response(status_code=204)
```

`app/main.py` の import を `from app.routers import ideas, tasks` に変え、`app.include_router(tasks.router)` の下に追加:
```python
app.include_router(ideas.router)
```

- [ ] **Step 5: テストが通ることを確認する**

Run: `.venv/bin/pytest -v`
Expected: all passed

- [ ] **Step 6: コミットする**

```bash
git add app tests
git commit -m "feat: アイディアの CRUD・検索 API を追加

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: ブレスト API と昇格

**Files:**
- Modify: `app/models.py`, `app/main.py`
- Create: `app/routers/brainstorm.py`
- Test: `tests/test_brainstorm.py`

**Interfaces:**
- Consumes: `fetch_idea`（Task 3）、`NonEmptyStr`（Task 2）
- Produces:
  - `app.models.BrainstormCreate`, `BrainstormOut`
  - `GET /api/brainstorm` → `BrainstormOut[]`（新しい順）
  - `POST /api/brainstorm` → 201 `BrainstormOut`
  - `DELETE /api/brainstorm/{id}` → 204
  - `POST /api/brainstorm/{id}/promote` → 201 `IdeaOut`（メモは削除される）
  - `BrainstormOut` の JSON: `{id, text, created_at}`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_brainstorm.py`:
```python
def add(client, text):
    r = client.post("/api/brainstorm", json={"text": text})
    assert r.status_code == 201, r.text
    return r.json()


def test_add_and_list_newest_first(client):
    a = add(client, "一つ目")
    b = add(client, "二つ目")
    assert [x["id"] for x in client.get("/api/brainstorm").json()] == [b["id"], a["id"]]


def test_text_is_stripped(client):
    assert add(client, "  メモ  ")["text"] == "メモ"


def test_blank_text_rejected(client):
    assert client.post("/api/brainstorm", json={"text": "   "}).status_code == 422


def test_delete(client):
    a = add(client, "消す")
    assert client.delete(f"/api/brainstorm/{a['id']}").status_code == 204
    assert client.get("/api/brainstorm").json() == []


def test_promote_creates_idea_and_removes_memo(client):
    a = add(client, "新サービス案")
    r = client.post(f"/api/brainstorm/{a['id']}/promote")
    assert r.status_code == 201
    idea = r.json()
    assert idea["title"] == "新サービス案"
    assert idea["body"] == ""
    assert idea["task_count"] == 0
    assert client.get("/api/brainstorm").json() == []
    assert client.get(f"/api/ideas/{idea['id']}").json() == idea


def test_missing_memo_is_404(client):
    assert client.delete("/api/brainstorm/999").status_code == 404
    assert client.post("/api/brainstorm/999/promote").status_code == 404
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `.venv/bin/pytest tests/test_brainstorm.py -v`
Expected: FAIL（`/api/brainstorm` が 404/405）

- [ ] **Step 3: モデルを追加する**

`app/models.py` の末尾に追加:
```python
class BrainstormCreate(BaseModel):
    # 昇格するとそのままアイディアのタイトルになるので、タイトルと同じ制約にする
    text: NonEmptyStr


class BrainstormOut(BaseModel):
    id: int
    text: str
    created_at: str
```

- [ ] **Step 4: ルーターを実装する**

`app/routers/brainstorm.py`:
```python
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response

from app.db import get_conn, now_iso
from app.models import BrainstormCreate, BrainstormOut, IdeaOut
from app.routers.ideas import fetch_idea

router = APIRouter(prefix="/api", tags=["brainstorm"])


def _get_memo(conn: sqlite3.Connection, memo_id: int) -> dict:
    row = conn.execute("SELECT * FROM brainstorm WHERE id = ?", (memo_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="メモが見つかりません")
    return dict(row)


@router.get("/brainstorm", response_model=list[BrainstormOut])
def list_memos(conn: sqlite3.Connection = Depends(get_conn)):
    return [dict(r) for r in conn.execute("SELECT * FROM brainstorm ORDER BY created_at DESC, id DESC")]


@router.post("/brainstorm", response_model=BrainstormOut, status_code=201)
def add_memo(body: BrainstormCreate, conn: sqlite3.Connection = Depends(get_conn)):
    cur = conn.execute(
        "INSERT INTO brainstorm (text, created_at) VALUES (?, ?)", (body.text, now_iso())
    )
    conn.commit()
    return _get_memo(conn, cur.lastrowid)


@router.delete("/brainstorm/{memo_id}", status_code=204)
def delete_memo(memo_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    _get_memo(conn, memo_id)
    conn.execute("DELETE FROM brainstorm WHERE id = ?", (memo_id,))
    conn.commit()
    return Response(status_code=204)


@router.post("/brainstorm/{memo_id}/promote", response_model=IdeaOut, status_code=201)
def promote_memo(memo_id: int, conn: sqlite3.Connection = Depends(get_conn)):
    memo = _get_memo(conn, memo_id)
    now = now_iso()
    cur = conn.execute(
        "INSERT INTO ideas (title, body, created_at, updated_at) VALUES (?, '', ?, ?)",
        (memo["text"], now, now),
    )
    conn.execute("DELETE FROM brainstorm WHERE id = ?", (memo_id,))
    conn.commit()
    return fetch_idea(conn, cur.lastrowid)
```

`app/main.py` の import を `from app.routers import brainstorm, ideas, tasks` に変え、`app.include_router(ideas.router)` の下に追加:
```python
app.include_router(brainstorm.router)
```

- [ ] **Step 5: テストが通ることを確認する**

Run: `.venv/bin/pytest -v`
Expected: all passed

- [ ] **Step 6: コミットする**

```bash
git add app tests
git commit -m "feat: ブレストメモ API とアイディアへの昇格を追加

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: 画面の骨組み（レイアウト・共通 JS）

**Files:**
- Modify: `static/index.html`（全面置き換え）
- Create: `static/style.css`, `static/ui.js`, `static/dates.js`, `static/api.js`, `static/main.js`（仮版。Task 8 で完成させる）
- Test: 既存の `tests/test_app.py::test_index_is_served` がそのまま通ること＋ブラウザで確認

**Interfaces:**
- Consumes: Task 2〜4 の全 API
- Produces:
  - `ui.js`: `el(tag, attrs = {}, ...children) -> HTMLElement`、`toast(message: string) -> void`
  - `dates.js`: `parseDateTime(s) -> Date`、`startOfDay(d) -> Date`、`addDays(d, n) -> Date`、`startOfWeek(d) -> Date`（月曜始まり）、`dayDiff(a, b) -> number`（b − a の日数）、`toInputValue(d) -> "YYYY-MM-DDTHH:MM"`、`formatShort(s) -> "M/D HH:MM"`、`isWeekend(d) -> boolean`
  - `api.js`: `api.listTasks(area?)`, `api.createTask(t)`, `api.updateTask(id, patch)`, `api.deleteTask(id)`, `api.listAreas()`, `api.listIdeas(q?)`, `api.getIdea(id)`, `api.createIdea(i)`, `api.updateIdea(id, patch)`, `api.deleteIdea(id)`, `api.listMemos()`, `api.addMemo(text)`, `api.deleteMemo(id)`, `api.promoteMemo(id)`。失敗したら `Error(message)` を投げる（message はサーバーの `detail` が文字列ならそれ、配列なら「入力内容を確認してください」）
  - `index.html` の要素 ID（後続タスクが使う）: `area-filter`, `scale-week`, `scale-month`, `prev`, `today`, `next`, `range-label`, `add-task`, `gantt`, `add-idea`, `idea-search`, `idea-list`, `idea-editor`, `idea-title`, `idea-body`, `idea-status`, `idea-to-task`, `idea-delete`, `bs-input`, `bs-list`, `task-dialog`, `task-form`, `task-form-title`, `task-form-error`, `task-delete`, `task-cancel`, `area-options`, `related-options`, `toast-area`

- [ ] **Step 1: `static/index.html` を書く**

```html
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Task &amp; Idea Hub</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div class="app">
    <section class="pane pane-gantt">
      <header class="toolbar">
        <select id="area-filter" aria-label="領域で絞り込み">
          <option value="">すべての領域</option>
        </select>
        <div class="seg" role="group" aria-label="表示期間">
          <button id="scale-week" type="button" class="active">週</button>
          <button id="scale-month" type="button">月</button>
        </div>
        <button id="prev" type="button" aria-label="前へ">◀</button>
        <button id="today" type="button">今日</button>
        <button id="next" type="button" aria-label="次へ">▶</button>
        <span id="range-label" class="range-label"></span>
        <span class="spacer"></span>
        <button id="add-task" type="button" class="primary">＋ タスク</button>
      </header>
      <div id="gantt" class="gantt"></div>
    </section>

    <aside class="pane pane-side">
      <section class="panel ideas">
        <header class="panel-head">
          <h2>アイディア保管庫</h2>
          <button id="add-idea" type="button" aria-label="アイディアを追加">＋</button>
        </header>
        <input id="idea-search" type="search" placeholder="検索（タイトル・本文）">
        <ul id="idea-list" class="idea-list"></ul>
        <div id="idea-editor" class="idea-editor" hidden>
          <div class="editor-head">
            <input id="idea-title" aria-label="タイトル">
            <button id="idea-to-task" type="button" class="primary">タスク化</button>
            <button id="idea-delete" type="button" class="danger">削除</button>
          </div>
          <textarea id="idea-body" placeholder="アイディアを書く…"></textarea>
          <span id="idea-status" class="status"></span>
        </div>
      </section>

      <section class="panel brainstorm">
        <header class="panel-head"><h2>ブレスト</h2></header>
        <input id="bs-input" placeholder="思いつきを入力して Enter">
        <ul id="bs-list" class="bs-list"></ul>
      </section>
    </aside>
  </div>

  <dialog id="task-dialog">
    <form id="task-form">
      <h2 id="task-form-title">タスクを追加</h2>
      <label>領域<input name="area" list="area-options" required></label>
      <label>関連項目<input name="related" list="related-options"></label>
      <label>タスク名<input name="title" required></label>
      <label>開始日時<input name="start_at" type="datetime-local" required></label>
      <label>期限<input name="due_at" type="datetime-local" required></label>
      <label>優先度
        <select name="priority">
          <option value="high">高</option>
          <option value="mid">中</option>
          <option value="low">低</option>
        </select>
      </label>
      <label class="check"><input name="done" type="checkbox">完了</label>
      <p id="task-form-error" class="form-error"></p>
      <div class="actions">
        <button id="task-delete" type="button" class="danger">削除</button>
        <span class="spacer"></span>
        <button id="task-cancel" type="button">キャンセル</button>
        <button type="submit" class="primary">保存</button>
      </div>
    </form>
  </dialog>

  <datalist id="area-options"></datalist>
  <datalist id="related-options"></datalist>
  <div id="toast-area" class="toast-area" aria-live="polite"></div>

  <script type="module" src="main.js"></script>
</body>
</html>
```

- [ ] **Step 2: `static/style.css` を書く**

```css
:root {
  --bg: #ffffff;
  --bg-soft: #f6f7f9;
  --line: #e3e5e8;
  --text: #1f2328;
  --muted: #6b7280;
  --accent: #2563eb;
  --high: #e5484d;
  --mid: #f59e0b;
  --low: #9ca3af;
  --danger: #b91c1c;
  --day-w: 40px;
  font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Noto Sans JP", sans-serif;
  color: var(--text);
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); }
button, input, select, textarea { font: inherit; }
button {
  border: 1px solid var(--line); background: var(--bg); border-radius: 6px;
  padding: 4px 10px; cursor: pointer;
}
button:hover { background: var(--bg-soft); }
button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
button.danger { color: var(--danger); }
input, select, textarea { border: 1px solid var(--line); border-radius: 6px; padding: 5px 8px; }
h2 { font-size: 14px; margin: 0; }
.spacer { flex: 1; }
[hidden] { display: none !important; }

.app { display: grid; grid-template-columns: 2fr 1fr; height: 100vh; }
.pane { min-width: 0; min-height: 0; display: flex; flex-direction: column; }
.pane-gantt { border-right: 1px solid var(--line); }

/* ツールバー */
.toolbar {
  display: flex; align-items: center; gap: 6px; padding: 8px 12px;
  border-bottom: 1px solid var(--line);
}
.seg { display: inline-flex; }
.seg button { border-radius: 0; }
.seg button:first-child { border-radius: 6px 0 0 6px; }
.seg button:last-child { border-radius: 0 6px 6px 0; border-left: none; }
.seg button.active { background: var(--text); color: #fff; }
.range-label { color: var(--muted); font-size: 13px; margin-left: 4px; }

/* ガント */
.gantt { flex: 1; overflow: auto; font-size: 13px; }
.g-row { display: flex; min-width: max-content; border-bottom: 1px solid var(--line); }
.g-row:not(.g-head):hover .g-cells, .g-row:not(.g-head):hover .g-track { background-color: var(--bg-soft); }
.g-row:not(.g-head) { cursor: pointer; }
.g-cells {
  display: grid; grid-template-columns: 76px 90px 180px 86px 86px 36px 30px;
  position: sticky; left: 0; z-index: 1; background: var(--bg);
  border-right: 1px solid var(--line);
}
.g-cells > * { padding: 7px 6px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.g-head { position: sticky; top: 0; z-index: 2; background: var(--bg); font-weight: 600; }
.g-head .g-cells { z-index: 3; }
.g-track {
  position: relative; background-color: var(--bg);
  background-image: linear-gradient(to right, var(--line) 1px, transparent 1px);
  background-size: var(--day-w) 100%;
}
.g-head .g-track { display: flex; background-image: none; }
.g-day { width: var(--day-w); flex: none; text-align: center; padding: 3px 0; font-size: 11px; line-height: 1.3; }
.g-day.weekend { color: var(--muted); background: var(--bg-soft); }
.g-day.is-today { color: var(--accent); }
.g-bar { position: absolute; top: 8px; height: 16px; border-radius: 4px; }
.g-bar.high { background: var(--high); }
.g-bar.mid { background: var(--mid); }
.g-bar.low { background: var(--low); }
.g-today { position: absolute; top: 0; bottom: 0; width: 2px; background: var(--accent); opacity: .6; }
.prio { font-weight: 600; }
.prio.high { color: var(--high); }
.prio.mid { color: var(--mid); }
.prio.low { color: var(--low); }
.g-row.done .g-bar { opacity: .3; }
.g-row.done .g-title { text-decoration: line-through; color: var(--muted); }
.g-row.overdue .g-bar { outline: 2px solid var(--danger); outline-offset: 1px; }
.g-row.overdue .g-due { color: var(--danger); font-weight: 600; }
.g-empty { padding: 24px; color: var(--muted); }

/* 右側パネル */
.panel { display: flex; flex-direction: column; gap: 8px; padding: 10px 12px; min-height: 0; }
.ideas { flex: 3; border-bottom: 1px solid var(--line); }
.brainstorm { flex: 2; }
.panel-head { display: flex; align-items: center; justify-content: space-between; }
.idea-list, .bs-list { list-style: none; margin: 0; padding: 0; overflow: auto; }
.idea-list { max-height: 30%; flex: none; border: 1px solid var(--line); border-radius: 6px; }
.idea-list li { display: flex; gap: 6px; padding: 5px 8px; cursor: pointer; border-bottom: 1px solid var(--line); }
.idea-list li:last-child { border-bottom: none; }
.idea-list li.selected { background: #e8efff; }
.idea-list .idea-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.idea-list .badge { color: var(--accent); }
.idea-list li.empty, .bs-list li.empty { color: var(--muted); cursor: default; }
.idea-editor { flex: 1; display: flex; flex-direction: column; gap: 6px; min-height: 0; }
.editor-head { display: flex; gap: 6px; }
.editor-head input { flex: 1; min-width: 0; font-weight: 600; }
.idea-editor textarea { flex: 1; resize: none; line-height: 1.6; min-height: 80px; }
.status { font-size: 12px; color: var(--muted); }
.bs-list { flex: 1; }
.bs-list li { display: flex; align-items: center; gap: 6px; padding: 5px 2px; border-bottom: 1px dashed var(--line); }
.bs-list .bs-text { flex: 1; word-break: break-word; }
.bs-list button { padding: 2px 6px; font-size: 12px; }

/* ダイアログ */
dialog { border: 1px solid var(--line); border-radius: 10px; padding: 18px; width: 380px; }
dialog::backdrop { background: rgba(0, 0, 0, .25); }
#task-form { display: flex; flex-direction: column; gap: 10px; }
#task-form label { display: flex; flex-direction: column; gap: 3px; font-size: 13px; color: var(--muted); }
#task-form label.check { flex-direction: row; align-items: center; gap: 6px; }
#task-form .actions { display: flex; gap: 6px; }
.form-error { color: var(--danger); margin: 0; min-height: 1em; font-size: 13px; }

/* トースト */
.toast-area { position: fixed; right: 16px; bottom: 16px; display: flex; flex-direction: column; gap: 6px; z-index: 10; }
.toast { background: var(--text); color: #fff; padding: 8px 14px; border-radius: 6px; font-size: 13px; }
```

- [ ] **Step 3: `static/ui.js` を書く**

```js
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "style") node.style.cssText = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : String(child));
  }
  return node;
}

export function toast(message) {
  const area = document.getElementById("toast-area");
  const node = el("div", { class: "toast" }, message);
  area.append(node);
  setTimeout(() => node.remove(), 4000);
}
```

- [ ] **Step 4: `static/dates.js` を書く**

```js
const DAY_MS = 24 * 60 * 60 * 1000;
const pad = (n) => String(n).padStart(2, "0");

// "YYYY-MM-DDTHH:MM" はタイムゾーンなしなのでローカル時刻として解釈される
export function parseDateTime(s) {
  return new Date(s);
}

export function startOfDay(d) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

export function addDays(d, n) {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

export function startOfWeek(d) {
  const day = startOfDay(d);
  const offset = (day.getDay() + 6) % 7; // 月曜 = 0
  return addDays(day, -offset);
}

export function dayDiff(a, b) {
  return Math.round((startOfDay(b) - startOfDay(a)) / DAY_MS);
}

export function toInputValue(d) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function formatShort(s) {
  const d = parseDateTime(s);
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function isWeekend(d) {
  return d.getDay() === 0 || d.getDay() === 6;
}
```

- [ ] **Step 5: `static/api.js` を書く**

```js
async function request(method, path, body) {
  const options = { method, headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(path, options);
  } catch {
    throw new Error("サーバーに接続できません");
  }
  if (!res.ok) {
    let message = `エラーが発生しました (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail)) message = "入力内容を確認してください";
    } catch {
      // JSON でない応答は既定のメッセージのまま
    }
    throw new Error(message);
  }
  return res.status === 204 ? null : res.json();
}

const q = (params) => {
  const s = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString();
  return s ? `?${s}` : "";
};

export const api = {
  listTasks: (area) => request("GET", `/api/tasks${q({ area })}`),
  createTask: (task) => request("POST", "/api/tasks", task),
  updateTask: (id, patch) => request("PATCH", `/api/tasks/${id}`, patch),
  deleteTask: (id) => request("DELETE", `/api/tasks/${id}`),
  listAreas: () => request("GET", "/api/areas"),
  listIdeas: (search) => request("GET", `/api/ideas${q({ q: search })}`),
  getIdea: (id) => request("GET", `/api/ideas/${id}`),
  createIdea: (idea) => request("POST", "/api/ideas", idea),
  updateIdea: (id, patch) => request("PATCH", `/api/ideas/${id}`, patch),
  deleteIdea: (id) => request("DELETE", `/api/ideas/${id}`),
  listMemos: () => request("GET", "/api/brainstorm"),
  addMemo: (text) => request("POST", "/api/brainstorm", { text }),
  deleteMemo: (id) => request("DELETE", `/api/brainstorm/${id}`),
  promoteMemo: (id) => request("POST", `/api/brainstorm/${id}/promote`),
};
```

- [ ] **Step 6: 仮の `static/main.js` を書く（API 疎通の確認用。Task 8 で置き換える）**

```js
import { api } from "./api.js";
import { toast } from "./ui.js";

api.listTasks()
  .then((tasks) => toast(`API 接続 OK（タスク ${tasks.length} 件）`))
  .catch((err) => toast(err.message));
```

- [ ] **Step 7: テストとブラウザで確認する**

Run: `.venv/bin/pytest -v`
Expected: all passed

Run（別ターミナル）: `./run.sh`
ブラウザで `http://localhost:5003` を開く。
Expected: 左 2/3 にツールバー、右 1/3 に「アイディア保管庫」と「ブレスト」の見出しが表示され、右下に「API 接続 OK（タスク 0 件）」のトーストが出る。ブラウザのコンソールにエラーがない。

- [ ] **Step 8: コミットする**

```bash
git add static
git commit -m "feat: 3ペインのレイアウトと共通 JS（ui・dates・api）を追加

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: ガントチャートとタスクダイアログ

**Files:**
- Create: `static/gantt.js`, `static/taskForm.js`
- Modify: `static/main.js`（ガントとダイアログをつなぐ版に置き換え）

**Interfaces:**
- Consumes: `el`, `toast`（ui.js）、dates.js の全関数、`api.listTasks` / `createTask` / `updateTask` / `deleteTask` / `listAreas`
- Produces:
  - `gantt.js`: `createGantt(root: HTMLElement, { onEdit(task), onToggleDone(task, done) }) -> { render(tasks), setScale("week"|"month"), shift(direction: -1|1), goToday(), rangeLabel(): string }`
  - `taskForm.js`: `initTaskForm({ onSaved(task|null, { deleted: boolean }) }) -> { open({ task?, defaults? }), setOptions({ areas: string[], related: string[] }) }`
    - `task` を渡すと編集、渡さないと新規作成。`defaults` は新規時の初期値（`idea_id` を含められる）

- [ ] **Step 1: `static/gantt.js` を書く**

```js
import { addDays, dayDiff, formatShort, isWeekend, parseDateTime, startOfDay, startOfWeek } from "./dates.js";
import { el } from "./ui.js";

const SCALES = {
  week: { days: 14, dayWidth: 40 },
  month: { dayWidth: 22 },
};
const PRIORITY_LABEL = { high: "高", mid: "中", low: "低" };
const COLUMNS = ["領域", "関連項目", "タスク名", "開始", "期限", "優先", "完了"];

function computeRange(scale, anchor) {
  if (scale === "week") {
    return { start: startOfWeek(anchor), days: SCALES.week.days, dayWidth: SCALES.week.dayWidth };
  }
  const start = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
  const days = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0).getDate();
  return { start, days, dayWidth: SCALES.month.dayWidth };
}

function sortTasks(tasks) {
  return [...tasks].sort(
    (a, b) => a.area.localeCompare(b.area, "ja") || a.start_at.localeCompare(b.start_at) || a.id - b.id,
  );
}

export function createGantt(root, { onEdit, onToggleDone }) {
  let scale = "week";
  let anchor = startOfDay(new Date());
  let tasks = [];

  function headerRow(range) {
    const today = startOfDay(new Date());
    const days = [];
    for (let i = 0; i < range.days; i++) {
      const d = addDays(range.start, i);
      const showMonth = i === 0 || d.getDate() === 1;
      days.push(el("div", {
        class: `g-day${isWeekend(d) ? " weekend" : ""}${dayDiff(today, d) === 0 ? " is-today" : ""}`,
      }, showMonth ? `${d.getMonth() + 1}/` : "", el("br"), String(d.getDate())));
    }
    return el("div", { class: "g-row g-head" },
      el("div", { class: "g-cells" }, COLUMNS.map((c) => el("div", {}, c))),
      el("div", { class: "g-track" }, days));
  }

  function taskRow(task, range, now) {
    const start = parseDateTime(task.start_at);
    const due = parseDateTime(task.due_at);
    const overdue = !task.done && due < now;
    const checkbox = el("input", {
      type: "checkbox",
      checked: task.done,
      "aria-label": "完了",
      onclick: (e) => e.stopPropagation(),
      onchange: (e) => onToggleDone(task, e.target.checked),
    });

    const track = el("div", { class: "g-track", style: `width:${range.days * range.dayWidth}px` });
    const first = Math.max(dayDiff(range.start, start), 0);
    const last = Math.min(dayDiff(range.start, due), range.days - 1);
    if (last >= 0 && first <= range.days - 1 && first <= last) {
      track.append(el("div", {
        class: `g-bar ${task.priority}`,
        title: `${task.title}\n${formatShort(task.start_at)} 〜 ${formatShort(task.due_at)}`,
        style: `left:${first * range.dayWidth + 2}px;width:${(last - first + 1) * range.dayWidth - 4}px`,
      }));
    }
    const todayIndex = dayDiff(range.start, now);
    if (todayIndex >= 0 && todayIndex < range.days) {
      track.append(el("div", {
        class: "g-today",
        style: `left:${todayIndex * range.dayWidth + range.dayWidth / 2}px`,
      }));
    }

    return el("div", {
      class: `g-row${task.done ? " done" : ""}${overdue ? " overdue" : ""}`,
      onclick: () => onEdit(task),
    },
      el("div", { class: "g-cells" },
        el("div", { title: task.area }, task.area),
        el("div", { title: task.related }, task.related),
        el("div", { class: "g-title", title: task.title }, task.title),
        el("div", {}, formatShort(task.start_at)),
        el("div", { class: "g-due" }, formatShort(task.due_at)),
        el("div", { class: `prio ${task.priority}` }, PRIORITY_LABEL[task.priority]),
        el("div", {}, checkbox)),
      track);
  }

  function render(nextTasks = tasks) {
    tasks = nextTasks;
    const range = computeRange(scale, anchor);
    root.style.setProperty("--day-w", `${range.dayWidth}px`);
    const now = new Date();
    const rows = sortTasks(tasks).map((t) => taskRow(t, range, now));
    root.replaceChildren(
      headerRow(range),
      ...(rows.length ? rows : [el("div", { class: "g-empty" }, "タスクがありません。「＋ タスク」から追加できます。")]),
    );
  }

  function rangeLabel() {
    const range = computeRange(scale, anchor);
    const end = addDays(range.start, range.days - 1);
    const f = (d) => `${d.getFullYear()}/${d.getMonth() + 1}/${d.getDate()}`;
    return `${f(range.start)} 〜 ${f(end)}`;
  }

  return {
    render,
    rangeLabel,
    setScale(next) {
      scale = next;
      render();
    },
    shift(direction) {
      anchor = scale === "week"
        ? addDays(anchor, 7 * direction)
        : new Date(anchor.getFullYear(), anchor.getMonth() + direction, 1);
      render();
    },
    goToday() {
      anchor = startOfDay(new Date());
      render();
    },
  };
}
```

- [ ] **Step 2: `static/taskForm.js` を書く**

```js
import { api } from "./api.js";
import { addDays, toInputValue } from "./dates.js";
import { el } from "./ui.js";

function defaultTimes() {
  const start = new Date();
  start.setHours(9, 0, 0, 0);
  const due = addDays(start, 7);
  due.setHours(18, 0, 0, 0);
  return { start_at: toInputValue(start), due_at: toInputValue(due) };
}

export function initTaskForm({ onSaved }) {
  const dialog = document.getElementById("task-dialog");
  const form = document.getElementById("task-form");
  const heading = document.getElementById("task-form-title");
  const errorBox = document.getElementById("task-form-error");
  const deleteButton = document.getElementById("task-delete");
  // form.title は HTMLElement の title 属性と衝突するため namedItem で取得する
  const field = (name) => form.elements.namedItem(name);

  let editing = null;
  let ideaId = null;

  function open({ task = null, defaults = {} } = {}) {
    editing = task;
    ideaId = task ? task.idea_id : (defaults.idea_id ?? null);
    const values = task ?? {
      area: "", related: "", title: "", priority: "mid", done: false, ...defaultTimes(), ...defaults,
    };
    for (const name of ["area", "related", "title", "start_at", "due_at", "priority"]) {
      field(name).value = values[name] ?? "";
    }
    field("done").checked = Boolean(values.done);
    heading.textContent = task ? "タスクを編集" : "タスクを追加";
    deleteButton.hidden = !task;
    errorBox.textContent = "";
    dialog.showModal();
    field(values.area ? "title" : "area").focus();
  }

  function readForm() {
    return {
      area: field("area").value.trim(),
      related: field("related").value.trim(),
      title: field("title").value.trim(),
      start_at: field("start_at").value,
      due_at: field("due_at").value,
      priority: field("priority").value,
      done: field("done").checked,
    };
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = readForm();
    if (!payload.area || !payload.title) {
      errorBox.textContent = "領域とタスク名は必須です";
      return;
    }
    if (payload.due_at < payload.start_at) {
      errorBox.textContent = "期限は開始日時以降にしてください";
      return;
    }
    try {
      const saved = editing
        ? await api.updateTask(editing.id, payload)
        : await api.createTask({ ...payload, idea_id: ideaId });
      dialog.close();
      onSaved(saved, { deleted: false });
    } catch (err) {
      errorBox.textContent = err.message;
    }
  });

  deleteButton.addEventListener("click", async () => {
    if (!editing || !confirm(`「${editing.title}」を削除しますか？`)) return;
    try {
      await api.deleteTask(editing.id);
      dialog.close();
      onSaved(null, { deleted: true });
    } catch (err) {
      errorBox.textContent = err.message;
    }
  });

  document.getElementById("task-cancel").addEventListener("click", () => dialog.close());

  function setOptions({ areas, related }) {
    const fill = (id, values) =>
      document.getElementById(id).replaceChildren(...values.map((v) => el("option", { value: v })));
    fill("area-options", areas);
    fill("related-options", related);
  }

  return { open, setOptions };
}
```

- [ ] **Step 3: `static/main.js` をガント対応版に置き換える**

```js
import { api } from "./api.js";
import { createGantt } from "./gantt.js";
import { initTaskForm } from "./taskForm.js";
import { el, toast } from "./ui.js";

const areaFilter = document.getElementById("area-filter");
const rangeLabel = document.getElementById("range-label");
let tasks = [];

const gantt = createGantt(document.getElementById("gantt"), {
  onEdit: (task) => taskForm.open({ task }),
  onToggleDone: async (task, done) => {
    try {
      await api.updateTask(task.id, { done });
      await loadTasks();
    } catch (err) {
      toast(err.message);
      await loadTasks();
    }
  },
});

const taskForm = initTaskForm({
  onSaved: async () => {
    await loadTasks();
  },
});

function renderGantt() {
  gantt.render(tasks);
  rangeLabel.textContent = gantt.rangeLabel();
}

async function loadTasks() {
  try {
    const [areas, loaded] = await Promise.all([api.listAreas(), api.listTasks(areaFilter.value)]);
    tasks = loaded;
    const selected = areaFilter.value;
    areaFilter.replaceChildren(
      el("option", { value: "" }, "すべての領域"),
      ...areas.map((a) => el("option", { value: a }, a)),
    );
    // 絞り込み中の領域がタスク削除で消えた場合は「すべて」に戻す
    areaFilter.value = areas.includes(selected) ? selected : "";
    if (areaFilter.value !== selected) tasks = await api.listTasks("");
    const related = [...new Set(tasks.map((t) => t.related).filter(Boolean))].sort();
    taskForm.setOptions({ areas, related });
    renderGantt();
  } catch (err) {
    toast(err.message);
  }
}

function setScale(scale) {
  document.getElementById("scale-week").classList.toggle("active", scale === "week");
  document.getElementById("scale-month").classList.toggle("active", scale === "month");
  gantt.setScale(scale);
  rangeLabel.textContent = gantt.rangeLabel();
}

areaFilter.addEventListener("change", loadTasks);
document.getElementById("scale-week").addEventListener("click", () => setScale("week"));
document.getElementById("scale-month").addEventListener("click", () => setScale("month"));
document.getElementById("prev").addEventListener("click", () => { gantt.shift(-1); rangeLabel.textContent = gantt.rangeLabel(); });
document.getElementById("next").addEventListener("click", () => { gantt.shift(1); rangeLabel.textContent = gantt.rangeLabel(); });
document.getElementById("today").addEventListener("click", () => { gantt.goToday(); rangeLabel.textContent = gantt.rangeLabel(); });
document.getElementById("add-task").addEventListener("click", () => taskForm.open());

loadTasks();
```

- [ ] **Step 4: ブラウザで確認する**

Run: `./run.sh`（起動中なら再読み込みのみ）。`http://localhost:5003` を開く。

確認項目（すべて満たすこと）:
1. 「＋ タスク」→ 領域「仕事」、関連項目「PJ-A」、タスク名「資料作成」、優先度「高」で保存すると、今週の表示に赤いバーが出る
2. 期限を開始より前にして保存すると、ダイアログ内に「期限は開始日時以降にしてください」と表示され、保存されない
3. 行をクリックすると編集ダイアログが開き、変更して保存すると反映される。「削除」で確認後に消える
4. 完了チェックを入れると、バーが薄くなりタスク名に取り消し線が付く。再読み込みしても残る
5. 期限が過去で未完了のタスクは、期限が赤字になりバーに赤枠が付く
6. 「月」に切り替えると当月 1 日〜月末が表示される。◀▶ で期間が移動し、「今日」で今日を含む期間に戻る。今日の位置に青い縦線がある
7. 表示期間の途中から始まる・途中で終わるタスク（例：先月開始〜来月期限）は、バーが表示期間の端で切り取られて表示される
8. 領域を 2 種類登録し、領域ドロップダウンで絞り込める。新規ダイアログの領域欄に既存の領域が候補として出る

Run: `.venv/bin/pytest -v`
Expected: all passed

- [ ] **Step 5: コミットする**

```bash
git add static
git commit -m "feat: ガントチャートとタスク編集ダイアログを追加

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: アイディア保管庫パネル（タスク化を含む）

**Files:**
- Create: `static/ideas.js`
- Modify: `static/main.js`

**Interfaces:**
- Consumes: `api.listIdeas` / `getIdea` / `createIdea` / `updateIdea` / `deleteIdea`、`el`、`toast`、Task 6 の `taskForm.open({ defaults })`
- Produces:
  - `ideas.js`: `initIdeas({ onMakeTask(idea) }) -> { refresh(): Promise<void>, reveal(id: number): Promise<void> }`
    - `reveal(id)` は検索欄を空にして一覧を読み直し、そのアイディアを選択する（Task 8 の昇格で使う）

- [ ] **Step 1: `static/ideas.js` を書く**

```js
import { api } from "./api.js";
import { el, toast } from "./ui.js";

const AUTOSAVE_MS = 800;
const SEARCH_MS = 300;

export function initIdeas({ onMakeTask }) {
  const list = document.getElementById("idea-list");
  const search = document.getElementById("idea-search");
  const editor = document.getElementById("idea-editor");
  const titleInput = document.getElementById("idea-title");
  const bodyInput = document.getElementById("idea-body");
  const status = document.getElementById("idea-status");

  let ideas = [];
  let selectedId = null;
  let saveTimer = null;
  let searchTimer = null;

  function renderList() {
    if (!ideas.length) {
      list.replaceChildren(el("li", { class: "empty" }, search.value.trim() ? "該当なし" : "アイディアはまだありません"));
      return;
    }
    list.replaceChildren(...ideas.map((idea) =>
      el("li", { class: idea.id === selectedId ? "selected" : "", onclick: () => select(idea.id) },
        el("span", { class: "idea-title", title: idea.title }, idea.title),
        idea.task_count > 0 ? el("span", { class: "badge", title: "タスク化済み" }, "✓") : null)));
  }

  async function refresh() {
    try {
      ideas = await api.listIdeas(search.value.trim());
      renderList();
    } catch (err) {
      toast(err.message);
    }
  }

  async function save() {
    saveTimer = null;
    if (selectedId === null) return;
    const title = titleInput.value.trim();
    if (!title) {
      status.textContent = "タイトルは必須です（未保存）";
      return;
    }
    try {
      const updated = await api.updateIdea(selectedId, { title, body: bodyInput.value });
      status.textContent = "保存済み";
      const index = ideas.findIndex((i) => i.id === updated.id);
      if (index >= 0) {
        ideas[index] = updated;
        renderList();
      }
    } catch {
      // 次の入力で scheduleSave が再び呼ばれ、再試行される
      status.textContent = "保存失敗（次の入力で再試行します）";
    }
  }

  function scheduleSave() {
    status.textContent = "編集中…";
    clearTimeout(saveTimer);
    saveTimer = setTimeout(save, AUTOSAVE_MS);
  }

  async function flushSave() {
    if (saveTimer !== null) {
      clearTimeout(saveTimer);
      await save();
    }
  }

  async function select(id) {
    await flushSave();
    try {
      const idea = await api.getIdea(id);
      selectedId = idea.id;
      titleInput.value = idea.title;
      bodyInput.value = idea.body;
      status.textContent = "";
      editor.hidden = false;
      renderList();
    } catch (err) {
      toast(err.message);
    }
  }

  async function reveal(id) {
    search.value = "";
    await refresh();
    await select(id);
  }

  titleInput.addEventListener("input", scheduleSave);
  bodyInput.addEventListener("input", scheduleSave);
  search.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(refresh, SEARCH_MS);
  });

  document.getElementById("add-idea").addEventListener("click", async () => {
    try {
      const idea = await api.createIdea({ title: "新しいアイディア", body: "" });
      await reveal(idea.id);
      titleInput.select();
      titleInput.focus();
    } catch (err) {
      toast(err.message);
    }
  });

  document.getElementById("idea-delete").addEventListener("click", async () => {
    if (selectedId === null || !confirm(`「${titleInput.value}」を削除しますか？`)) return;
    clearTimeout(saveTimer);
    saveTimer = null;
    try {
      await api.deleteIdea(selectedId);
      selectedId = null;
      editor.hidden = true;
      await refresh();
    } catch (err) {
      toast(err.message);
    }
  });

  document.getElementById("idea-to-task").addEventListener("click", async () => {
    if (selectedId === null) return;
    await flushSave();
    onMakeTask({ id: selectedId, title: titleInput.value.trim() });
  });

  refresh();
  return { refresh, reveal };
}
```

- [ ] **Step 2: `static/main.js` を変更する**

import に追加:
```js
import { initIdeas } from "./ideas.js";
```

`const taskForm = initTaskForm({...});` を次に置き換える（タスク保存時に ✓ 表示を更新するため）:
```js
const taskForm = initTaskForm({
  onSaved: async () => {
    await Promise.all([loadTasks(), ideas.refresh()]);
  },
});

const ideas = initIdeas({
  onMakeTask: (idea) => taskForm.open({ defaults: { title: idea.title, idea_id: idea.id } }),
});
```

- [ ] **Step 3: ブラウザで確認する**

`http://localhost:5003` を再読み込みして確認する:
1. 保管庫の「＋」で「新しいアイディア」ができ、タイトルが選択状態になる。タイトルと本文を入力すると約 0.8 秒後に「保存済み」と表示され、再読み込み後も残る
2. タイトルを空にすると「タイトルは必須です（未保存）」と表示され、保存されない
3. 検索欄に本文中の語を入れると絞り込まれる。「100%」のような記号を含む語でも正しく検索できる
4. 「タスク化」を押すと、タスク名にアイディアのタイトルが入り、開始＝今日 9:00、期限＝7 日後 18:00、優先度＝中のダイアログが開く。領域を入れて保存すると、ガントにタスクが追加され、一覧のアイディアに ✓ が付く
5. タスク化したアイディアを削除しても、ガント上のタスクは残る
6. 入力直後（0.8 秒以内）に別のアイディアを選んでも、直前の入力が失われない

Run: `.venv/bin/pytest -v`
Expected: all passed

- [ ] **Step 4: コミットする**

```bash
git add static
git commit -m "feat: アイディア保管庫パネル（自動保存・検索・タスク化）を追加

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: ブレストパネル（昇格を含む）

**Files:**
- Create: `static/brainstorm.js`
- Modify: `static/main.js`

**Interfaces:**
- Consumes: `api.listMemos` / `addMemo` / `deleteMemo` / `promoteMemo`、`el`、`toast`、Task 7 の `ideas.reveal(id)`
- Produces: `brainstorm.js`: `initBrainstorm({ onPromoted(idea) }) -> { refresh(): Promise<void> }`

- [ ] **Step 1: `static/brainstorm.js` を書く**

```js
import { api } from "./api.js";
import { el, toast } from "./ui.js";

export function initBrainstorm({ onPromoted }) {
  const input = document.getElementById("bs-input");
  const list = document.getElementById("bs-list");

  function render(memos) {
    if (!memos.length) {
      list.replaceChildren(el("li", { class: "empty" }, "思いついたことを上の欄に書き留めましょう"));
      return;
    }
    list.replaceChildren(...memos.map((memo) =>
      el("li", {},
        el("span", { class: "bs-text" }, memo.text),
        el("button", { type: "button", title: "アイディア保管庫へ移す", onclick: () => promote(memo) }, "→保管庫"),
        el("button", { type: "button", title: "削除", "aria-label": "削除", onclick: () => remove(memo) }, "×"))));
  }

  async function refresh() {
    try {
      render(await api.listMemos());
    } catch (err) {
      toast(err.message);
    }
  }

  async function promote(memo) {
    try {
      const idea = await api.promoteMemo(memo.id);
      await refresh();
      await onPromoted(idea);
    } catch (err) {
      toast(err.message);
    }
  }

  async function remove(memo) {
    try {
      await api.deleteMemo(memo.id);
      await refresh();
    } catch (err) {
      toast(err.message);
    }
  }

  input.addEventListener("keydown", async (e) => {
    // 日本語入力の変換確定の Enter では追加しない
    if (e.key !== "Enter" || e.isComposing || e.keyCode === 229) return;
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    try {
      await api.addMemo(text);
      input.value = "";
      await refresh();
    } catch (err) {
      toast(err.message);
    }
    input.focus();
  });

  refresh();
  return { refresh };
}
```

- [ ] **Step 2: `static/main.js` を変更する**

import に追加:
```js
import { initBrainstorm } from "./brainstorm.js";
```

`const ideas = initIdeas({...});` の下に追加:
```js
initBrainstorm({
  onPromoted: (idea) => ideas.reveal(idea.id),
});
```

- [ ] **Step 3: ブラウザで確認する**

`http://localhost:5003` を再読み込みして確認する:
1. ブレスト欄に日本語で入力する。変換確定の Enter では追加されず、確定後にもう一度 Enter を押すと追加される。入力欄は空になり、フォーカスが残る
2. 続けて 3 件追加すると、新しい順に並ぶ
3. 「×」でメモが消える
4. 「→保管庫」でメモが一覧から消え、保管庫に同じタイトルのアイディアが追加されて選択状態になる（保管庫で検索中だった場合も、検索が解除されて表示される）
5. 空白だけの入力で Enter を押しても何も追加されない

Run: `.venv/bin/pytest -v`
Expected: all passed

- [ ] **Step 4: コミットする**

```bash
git add static
git commit -m "feat: ブレストパネルと保管庫への昇格を追加

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: 全体確認と README

**Files:**
- Create: `README.md`

- [ ] **Step 1: `README.md` を書く**

````markdown
# Task & Idea Hub

個人用のタスク管理（ガントチャート）・アイディア保管庫・ブレストメモを 1 画面で扱うローカル Web アプリ。

## セットアップ

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 起動

```bash
./run.sh
```

ブラウザで http://localhost:5003 を開く。

## データ

- 保存先: `data/app.db`（SQLite）。git 管理外
- バックアップ: サーバーを止めてから `data/app.db` をコピーする

## テスト

```bash
.venv/bin/pytest -v
```
````

- [ ] **Step 2: 全テストを実行する**

Run: `.venv/bin/pytest -v`
Expected: all passed、警告以外の出力なし

- [ ] **Step 3: 通しで操作確認する**

サーバーを一度止めて `./run.sh` で起動し直し、`http://localhost:5003` で次の流れを確認する:
1. ブレストに 2 件書く → 1 件を保管庫へ移す → 本文を書く → タスク化 → ガントに表示され ✓ が付く
2. タスクを完了にする → 期限切れのタスクを 1 件作り、赤く強調されることを確認する
3. サーバーを止めて起動し直し、再読み込みしてもすべてのデータが残っている
4. サーバーを止めた状態で操作すると、右下に「サーバーに接続できません」のトーストが出る
5. ブラウザのコンソールにエラーがない

- [ ] **Step 4: コミットする**

```bash
git add README.md
git commit -m "docs: README（起動・バックアップ・テスト手順）を追加

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
