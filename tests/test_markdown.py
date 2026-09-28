from app.markdown_render import render_markdown


def test_basic_formatting():
    html = render_markdown("# 見出し\n\n**太字** と *斜体* と ~~取り消し~~ と `code`")
    assert "<h1>見出し</h1>" in html
    assert "<strong>太字</strong>" in html
    assert "<em>斜体</em>" in html
    assert "<del>取り消し</del>" in html
    assert "<code>code</code>" in html


def test_fenced_code_is_not_formatted_inside():
    html = render_markdown("```python\nx = ~~1~~ **2**\n```")
    assert "<pre>" in html
    assert "~~1~~" in html
    assert "<del>" not in html


def test_lists_and_nested():
    html = render_markdown("- a\n    - b\n\n1. one\n2. two")
    assert html.count("<ul>") == 2
    assert "<ol>" in html


def test_two_space_nested_list():
    html = render_markdown("- a\n  - b\n    - c\n- d")
    assert html.count("<ul>") == 3


def test_table():
    html = render_markdown("| a | b |\n|---|---|\n| 1 | 2 |")
    assert "<table>" in html and "<td>1</td>" in html


def test_task_list_checkboxes():
    html = render_markdown("- [ ] 未完了\n- [x] 完了")
    assert html.count('type="checkbox"') == 2
    assert html.count("checked") == 1
    assert "[ ]" not in html


def test_single_newline_is_line_break():
    assert "<br" in render_markdown("1行目\n2行目")


def test_dangerous_html_is_removed():
    html = render_markdown('<script>alert(1)</script>\n\n<img src=x onerror="alert(1)">\n\n[x](javascript:alert(1))')
    assert "<script" not in html
    assert "onerror" not in html
    assert "javascript:" not in html


def test_links_are_kept_with_safe_rel():
    html = render_markdown("[例](https://example.com)")
    assert 'href="https://example.com"' in html
    assert "noopener" in html


def test_empty():
    assert render_markdown("") == ""


def test_render_api(client):
    r = client.post("/api/markdown", json={"blocks": ["# a", "b"]})
    assert r.status_code == 200
    assert r.json()["html"][0] == "<h1>a</h1>"
    assert len(r.json()["html"]) == 2


def test_code_block_indent_is_untouched():
    html = render_markdown("- a\n  - b\n\n```\n  - keep\n```")
    assert "  - keep" in html
