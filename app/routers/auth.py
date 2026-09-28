import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app import auth
from app.db import get_conn, now_iso
from app.models import LoginIn, PasswordChangeIn, SetupIn

router = APIRouter(prefix="/api/auth", tags=["auth"])


def set_session_cookie(response: Response, token: str) -> None:
    # JavaScript からは読めない・他のサイトからのリクエストには付かない Cookie にする
    response.set_cookie(
        auth.SESSION_COOKIE, token, max_age=auth.SESSION_MAX_AGE, httponly=True, samesite="lax", path="/"
    )


@router.get("/status")
def status(request: Request, conn: sqlite3.Connection = Depends(get_conn)):
    session = auth.find_session(conn, request.cookies.get(auth.SESSION_COOKIE))
    return {
        "needs_setup": auth.user_count(conn) == 0,
        "logged_in": session is not None,
        "username": session["username"] if session else None,
    }


@router.post("/setup", status_code=201)
def setup(body: SetupIn, response: Response, conn: sqlite3.Connection = Depends(get_conn)):
    """最初の 1 回だけ、アカウント（ユーザー名とパスワード）を作る。"""
    if auth.user_count(conn) > 0:
        raise HTTPException(status_code=409, detail="アカウントはすでに作成されています")
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
        (body.username, auth.hash_password(body.password), now_iso()),
    )
    conn.commit()
    set_session_cookie(response, auth.create_session(conn, cur.lastrowid))
    return {"username": body.username}


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, conn: sqlite3.Connection = Depends(get_conn)):
    key = request.client.host if request.client else "unknown"
    if auth.is_locked(key):
        raise HTTPException(status_code=429, detail="ログインの失敗が続いたため、10 分間ログインできません")
    user = auth.get_user(conn, body.username)
    if user is None or not auth.verify_password(body.password, user["password_hash"]):
        auth.record_failure(key)
        raise HTTPException(status_code=401, detail="ユーザー名またはパスワードが違います")
    auth.clear_failures(key)
    set_session_cookie(response, auth.create_session(conn, user["id"]))
    return {"username": user["username"]}


@router.post("/logout", status_code=204)
def logout(request: Request, conn: sqlite3.Connection = Depends(get_conn)):
    auth.delete_session(conn, request.cookies.get(auth.SESSION_COOKIE))
    response = Response(status_code=204)
    response.delete_cookie(auth.SESSION_COOKIE, path="/")
    return response


@router.get("/me")
def me(request: Request):
    return {"username": request.state.session["username"]}


@router.post("/password", status_code=204)
def change_password(body: PasswordChangeIn, request: Request, conn: sqlite3.Connection = Depends(get_conn)):
    session = request.state.session
    user = auth.get_user(conn, session["username"])
    if not auth.verify_password(body.current, user["password_hash"]):
        raise HTTPException(status_code=400, detail="現在のパスワードが違います")
    auth.set_password(conn, user["id"], body.new)
    # このブラウザ以外のログインは解除する
    auth.delete_sessions(conn, user["id"], keep_token=request.cookies.get(auth.SESSION_COOKIE))
    return Response(status_code=204)
