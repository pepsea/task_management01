"""ログイン（1 アカウント）: パスワードのハッシュ、ログイン状態（セッション）、ログイン失敗の制限。"""

import base64
import hashlib
import hmac
import secrets
import sqlite3
import time
from datetime import datetime, timedelta

SESSION_COOKIE = "session"
SESSION_DAYS = 30
SESSION_MAX_AGE = SESSION_DAYS * 24 * 60 * 60
# 使われたセッションの期限を延ばす間隔（毎回書き込まないように 1 日ごと）
RENEW_AFTER = timedelta(days=1)
MIN_PASSWORD_LENGTH = 8

# パスワードは scrypt（Python 標準）でハッシュにして保存する
SCRYPT_N, SCRYPT_R, SCRYPT_P, SCRYPT_LEN = 2**14, 8, 1, 32


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=SCRYPT_LEN)
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, digest = stored.split("$")
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(
            password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=len(expected)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


def _token_hash(token: str) -> str:
    # Cookie のトークンそのものは保存せず、ハッシュだけを保存する
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now()


def user_count(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]


def get_user(conn: sqlite3.Connection, username: str) -> dict | None:
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return dict(row) if row else None


def create_session(conn: sqlite3.Connection, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    now = _now()
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, created_at, renewed_at, expires_at) VALUES (?, ?, ?, ?, ?)",
        (_token_hash(token), user_id, now.isoformat(), now.isoformat(),
         (now + timedelta(days=SESSION_DAYS)).isoformat()),
    )
    conn.commit()
    return token


def find_session(conn: sqlite3.Connection, token: str | None) -> dict | None:
    if not token:
        return None
    row = conn.execute(
        """SELECT s.token_hash, s.user_id, s.renewed_at, u.username FROM sessions s
           JOIN users u ON u.id = s.user_id
           WHERE s.token_hash = ? AND s.expires_at > ?""",
        (_token_hash(token), _now().isoformat()),
    ).fetchone()
    return dict(row) if row else None


def renew_if_needed(conn: sqlite3.Connection, session: dict) -> bool:
    """最後の延長から 1 日以上たっていれば、期限を今から 30 日後に延ばす。延ばしたら True。"""
    now = _now()
    if now - datetime.fromisoformat(session["renewed_at"]) < RENEW_AFTER:
        return False
    conn.execute(
        "UPDATE sessions SET renewed_at = ?, expires_at = ? WHERE token_hash = ?",
        (now.isoformat(), (now + timedelta(days=SESSION_DAYS)).isoformat(), session["token_hash"]),
    )
    conn.commit()
    return True


def delete_session(conn: sqlite3.Connection, token: str | None) -> None:
    if token:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
        conn.commit()


def delete_sessions(conn: sqlite3.Connection, user_id: int, keep_token: str | None = None) -> None:
    """ユーザーのログインをすべて解除する（keep_token のものだけ残す）。"""
    keep = _token_hash(keep_token) if keep_token else ""
    conn.execute("DELETE FROM sessions WHERE user_id = ? AND token_hash != ?", (user_id, keep))
    conn.commit()


def set_password(conn: sqlite3.Connection, user_id: int, password: str) -> None:
    conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(password), user_id))
    conn.commit()


# ログイン失敗の制限: 同じ接続元から 10 分以内に 5 回失敗したら、10 分間ログインできない
MAX_FAILURES = 5
LOCK_SECONDS = 600
_failures: dict[str, list[float]] = {}


def _recent_failures(key: str) -> list[float]:
    cutoff = time.monotonic() - LOCK_SECONDS
    recent = [t for t in _failures.get(key, []) if t > cutoff]
    _failures[key] = recent
    return recent


def is_locked(key: str) -> bool:
    return len(_recent_failures(key)) >= MAX_FAILURES


def record_failure(key: str) -> None:
    _recent_failures(key).append(time.monotonic())


def clear_failures(key: str) -> None:
    _failures.pop(key, None)


def reset_login_attempts() -> None:
    _failures.clear()
