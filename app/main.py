from contextlib import asynccontextmanager
from pathlib import Path

from contextlib import closing

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import auth
from app.db import connect, init_db
from app.routers import auth as auth_router
from app.routers import backups, brainstorm, decisions, export, ideas, links, masters, notes, recurring, tags, tasks

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Task & Idea Hub", lifespan=lifespan)


# ログインしていなくても開けるパス（ログイン画面・初回設定画面とその部品、状態確認）
PUBLIC_PATHS = {
    "/login.html", "/setup.html", "/auth.js", "/style.css",
    "/api/health", "/api/auth/status", "/api/auth/login", "/api/auth/setup",
}


@app.middleware("http")
async def require_login(request: Request, call_next):
    """ログインしていなければ、API は 401、画面はログイン画面（アカウントが無ければ初回設定画面）へ。"""
    if request.url.path in PUBLIC_PATHS:
        return await call_next(request)
    token = request.cookies.get(auth.SESSION_COOKIE)
    with closing(connect()) as conn:
        session = auth.find_session(conn, token)
        if session is None:
            if request.url.path.startswith("/api/"):
                return JSONResponse({"detail": "ログインしてください"}, status_code=401)
            target = "/setup.html" if auth.user_count(conn) == 0 else "/login.html"
            return RedirectResponse(target, status_code=303)
        renewed = auth.renew_if_needed(conn, session)
    request.state.session = session
    response = await call_next(request)
    if renewed:
        # 期限を延ばしたので Cookie の有効期限も延ばす
        auth_router.set_session_cookie(response, token)
    return response


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


app.include_router(auth_router.router)
app.include_router(tasks.router)
app.include_router(recurring.router)
app.include_router(ideas.router)
app.include_router(brainstorm.router)
app.include_router(decisions.router)
app.include_router(tags.router)
app.include_router(masters.router)
app.include_router(notes.router)
app.include_router(links.router)
app.include_router(export.router)
app.include_router(backups.router)
# API ルーターはこの行より上で登録する（"/" のマウントは全パスに一致するため最後に置く）
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
