"""どのアプリでも同じように読める Markdown にする（エクスポート・コピー用）。

このアプリだけの書き方（蛍光ペン ==文== と、文字色 <span style="color:…">文</span>）を取り除き、
中の文章だけを残す。コード（``` のブロックと ` の中）は変えない。
static/noteExport.js の toPortableMarkdown と同じ処理。
"""

import re

FENCE = re.compile(r"^\s*```", re.M)
INLINE_CODE = re.compile(r"(`+[^`]*?`+)")
HIGHLIGHT = re.compile(r"==(?=\S)(.+?)(?<=\S)==", re.S)
COLOR_SPAN = re.compile(r'<span\s+style="\s*color\s*:[^"]*">(.*?)</span>', re.S)


def _strip(text: str) -> str:
    parts = INLINE_CODE.split(text)
    # 奇数番目は ` で囲まれたコードなのでそのまま
    return "".join(
        part if i % 2 else COLOR_SPAN.sub(r"\1", HIGHLIGHT.sub(r"\1", part)) for i, part in enumerate(parts)
    )


def to_portable_markdown(text: str) -> str:
    lines = text.split("\n")
    out: list[str] = []
    chunk: list[str] = []
    in_code = False
    for line in lines:
        if FENCE.match(line):
            if not in_code and chunk:
                out.append(_strip("\n".join(chunk)))
                chunk = []
            in_code = not in_code
            out.append(line)
        elif in_code:
            out.append(line)
        else:
            chunk.append(line)
    if chunk:
        out.append(_strip("\n".join(chunk)))
    return "\n".join(out)
