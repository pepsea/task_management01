# Task & Idea Hub

個人用のタスク管理（ガントチャート）・アイディア保管庫・ブレストメモを 1 画面で扱うローカル Web アプリ。

- 左 2/3: ガントチャート（日・週・月表示、ディシジョンポイント、タスクのメモ）
- 右 1/3: アイディア保管庫（タグ・検索・タスク化）とブレストメモ
- 「⚙ 登録」画面: 領域・関連項目・タグの管理

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
