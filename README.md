# Task & Idea Hub

個人用のタスク管理（ガントチャート）・アイディア保管庫・ブレスト・Markdown メモ帳を扱うローカル Web アプリ。

- TODO: ガントチャート（日・週・月表示、ディシジョンポイント、今日のタスク、リンクリスト、ブレスト）
- NOTES: Markdown メモ帳（Typora 風の編集、タグ、ピン留め、エクスポート）
- アイディア: アイディア保管庫（タグ・優先・並べ替え・タスク化）
- 登録: 領域・関連項目・タグの管理
- アーカイブ: アーカイブしたアイディア・メモ

## Docker で動かす（おすすめ）

```bash
docker compose up -d
```

ブラウザで http://localhost:5003 を開く。

- 停止: `docker compose down`
- アプリを更新したとき（git pull の後など）: `docker compose up -d --build`
- ログ: `docker compose logs -f`
- データは `./data/app.db` に保存され、コンテナを作り直しても消えない
- 標準ではこのパソコンからだけ開ける。社内の他の PC からも使う場合は `docker-compose.yml` の `ports` を `"5003:5003"` に変える
- Linux で動かす場合、`./data` はコンテナ内のユーザー（UID 1000）が書き込めるようにしておく

## Docker を使わずに動かす

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
./run.sh
```

ブラウザで http://localhost:5003 を開く。

## データ

- 保存先: `data/app.db`（SQLite）。git 管理外
- バックアップ: アプリを止めてから `data/app.db` をコピーする

## テスト

```bash
.venv/bin/pytest -v
```
