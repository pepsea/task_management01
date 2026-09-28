"""サーバーで実行する管理コマンド。

  パスワードの再設定:  python -m app.cli reset-password
  （Docker の場合）    docker compose exec -u appuser app python -m app.cli reset-password
"""

import argparse
import getpass
import sys
from contextlib import closing

from app import auth
from app.db import connect, init_db


def reset_password(new_password: str) -> str:
    """アカウントのパスワードを変更し、すべてのログインを解除する。ユーザー名を返す。"""
    if len(new_password) < auth.MIN_PASSWORD_LENGTH:
        raise ValueError(f"パスワードは {auth.MIN_PASSWORD_LENGTH} 文字以上にしてください")
    init_db()
    with closing(connect()) as conn:
        row = conn.execute("SELECT id, username FROM users ORDER BY id LIMIT 1").fetchone()
        if row is None:
            raise LookupError("アカウントがまだありません。ブラウザでアプリを開いて初回設定をしてください")
        auth.set_password(conn, row["id"], new_password)
        auth.delete_sessions(conn, row["id"])
        return row["username"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Task & Idea Hub の管理コマンド")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("reset-password", help="パスワードを再設定する（すべてのログインが解除される）")
    parser.parse_args(argv)

    password = getpass.getpass("新しいパスワード: ")
    if password != getpass.getpass("もう一度入力: "):
        print("パスワードが一致しません", file=sys.stderr)
        return 1
    try:
        username = reset_password(password)
    except (ValueError, LookupError) as err:
        print(err, file=sys.stderr)
        return 1
    print(f"「{username}」のパスワードを再設定しました。ブラウザで新しいパスワードでログインしてください")
    return 0


if __name__ == "__main__":
    sys.exit(main())
