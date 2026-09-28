from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.routers import brainstorm, decisions, ideas, masters, notes, tags, tasks

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Task & Idea Hub", lifespan=lifespan)


@app.middleware("http")
async def revalidate_static_files(request: Request, call_next):
    # 画面の HTML/JS/CSS は毎回サーバーに確認させる（変更がなければ 304 でキャッシュを使う）。
    # 更新後に古い JS がキャッシュに残り、モジュールの読み込みに失敗して画面が壊れるのを防ぐ
    response = await call_next(request)
    if not request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/api/health")
def health():
    return {"status": "ok"}


app.include_router(tasks.router)
app.include_router(ideas.router)
app.include_router(brainstorm.router)
app.include_router(decisions.router)
app.include_router(tags.router)
app.include_router(masters.router)
app.include_router(notes.router)
# API ルーターはこの行より上で登録する（"/" のマウントは全パスに一致するため最後に置く）
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
