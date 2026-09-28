from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.routers import brainstorm, decisions, ideas, masters, tags, tasks

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Task & Idea Hub", lifespan=lifespan)


@app.get("/api/health")
def health():
    return {"status": "ok"}


app.include_router(tasks.router)
app.include_router(ideas.router)
app.include_router(brainstorm.router)
app.include_router(decisions.router)
app.include_router(tags.router)
app.include_router(masters.router)
# API ルーターはこの行より上で登録する（"/" のマウントは全パスに一致するため最後に置く）
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
