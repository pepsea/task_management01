"""アプリのバージョン（Git のコミット番号と、Docker イメージを作った日時）。

Git のコマンドは使わず、.git/HEAD と refs を直接読む（Docker イメージには .git の
HEAD・refs・packed-refs だけを入れている）。作成日時は Docker のビルド時に BUILD_TIME に書く。
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _commit(git_dir: Path) -> str | None:
    try:
        head = (git_dir / "HEAD").read_text().strip()
    except OSError:
        return None
    if not head.startswith("ref: "):
        return head or None
    ref = head[5:]
    try:
        return (git_dir / ref).read_text().strip() or None
    except OSError:
        pass
    # git gc の後はブランチの位置が packed-refs にまとめられている
    try:
        for line in (git_dir / "packed-refs").read_text().splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1] == ref:
                return parts[0]
    except OSError:
        pass
    return None


def read_version(root: Path = ROOT) -> dict:
    commit = _commit(root / ".git")
    try:
        built_at = (root / "BUILD_TIME").read_text().strip() or None
    except OSError:
        built_at = None
    return {"commit": commit[:7] if commit else None, "built_at": built_at}
