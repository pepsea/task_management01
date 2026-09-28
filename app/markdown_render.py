"""Markdown を安全な HTML に変換する（メモ帳の表示用）。"""

import re

import markdown
import nh3
from markdown.extensions import Extension
from markdown.inlinepatterns import SimpleTagInlineProcessor

ALLOWED_TAGS = {
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "br", "hr", "strong", "em", "del", "code", "pre",
    "blockquote", "ul", "ol", "li", "a", "img", "table", "thead", "tbody", "tr", "th", "td", "input",
}
ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
    "code": {"class"},
    "li": {"class"},
    "input": {"type", "checked", "disabled"},
    "th": {"align", "style"},
    "td": {"align", "style"},
}

# 「- [ ] 」「- [x] 」の項目をチェックボックスにする（ゆるいリストの <li><p> にも対応）
TASK_ITEM = re.compile(r"<li>(\s*<p>)?\[( |x|X)\]\s*")


LIST_LINE = re.compile(r"^( +)([-*+]|\d+\.)\s")


def _normalize_list_indent(text: str) -> str:
    """入れ子リストの字下げを 4 スペース単位にそろえる。

    Python-Markdown は 4 スペースで入れ子を判定するが、2 スペースで書く人も多いので、
    リスト行の最小の字下げが 2〜3 スペースならその幅を 1 段として 4 スペースに換算する。
    """
    # コードブロック（``` で囲まれた部分）の中は対象外
    in_code = False
    list_lines = []
    for index, line in enumerate(text.splitlines()):
        if line.lstrip().startswith("```"):
            in_code = not in_code
        elif not in_code and (m := LIST_LINE.match(line)):
            list_lines.append((index, len(m.group(1))))
    unit = min((indent for _, indent in list_lines), default=4)
    if unit >= 4:
        return text
    lines = text.splitlines()
    for index, indent in list_lines:
        lines[index] = " " * (4 * round(indent / unit)) + lines[index][indent:]
    return "\n".join(lines)


class StrikethroughExtension(Extension):
    """~~text~~ を <del> にする（Python-Markdown 標準には無いため）。"""

    def extendMarkdown(self, md):
        md.inlinePatterns.register(SimpleTagInlineProcessor(r"(~{2})(.+?)~{2}", "del"), "del", 175)


def _task_item(match: re.Match) -> str:
    checked = " checked" if match.group(2) in ("x", "X") else ""
    return f'<li class="task-item">{match.group(1) or ""}<input type="checkbox" disabled{checked}> '


def render_markdown(text: str) -> str:
    if not text.strip():
        return ""
    # 変換器は状態を持つので、呼び出しごとに作る
    converter = markdown.Markdown(
        extensions=["tables", "fenced_code", "sane_lists", "nl2br", StrikethroughExtension()],
    )
    html = TASK_ITEM.sub(_task_item, converter.convert(_normalize_list_indent(text)))
    return nh3.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes={"http", "https", "mailto"},
        link_rel="noopener noreferrer",
    )
