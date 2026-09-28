#!/bin/sh
# コンテナの起動処理。データの保存先（/app/data）をアプリのユーザー（appuser）が書き込めるようにしてから、
# root の権限を捨てて appuser でアプリを動かす。
#
# Linux ではホストに ./data が無いと Docker が root の持ち物として作るため、そのままでは
# appuser が書き込めず「unable to open database file」で起動に失敗する。
set -e

DATA_DIR="$(dirname "${APP_DB_PATH:-/app/data/app.db}")"

if [ "$(id -u)" = "0" ]; then
    mkdir -p "$DATA_DIR"
    if ! setpriv --reuid=appuser --regid=appuser --init-groups test -w "$DATA_DIR"; then
        echo "entrypoint: $DATA_DIR を appuser が書き込めるように所有者を変更します" >&2
        chown -R appuser:appuser "$DATA_DIR"
    fi
    exec setpriv --reuid=appuser --regid=appuser --init-groups "$@"
fi

# docker run --user などで root 以外で起動された場合はそのまま動かす
exec "$@"
