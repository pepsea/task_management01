from app.markdown_portable import to_portable_markdown


def test_removes_highlight_and_color_but_keeps_text():
    text = '# 見出し\n==大事== と <span style="color:#dc2626">赤い文</span> と **太字**'
    assert to_portable_markdown(text) == "# 見出し\n大事 と 赤い文 と **太字**"


def test_keeps_standard_markdown():
    text = "- [ ] やる\n~~取り消し~~\n| a | b |\n|---|---|\n| 1 | 2 |"
    assert to_portable_markdown(text) == text


def test_code_is_untouched():
    text = "`==x==` と ==y==\n\n```\n==z== <span style=\"color:red\">c</span>\n```"
    assert to_portable_markdown(text) == "`==x==` と y\n\n```\n==z== <span style=\"color:red\">c</span>\n```"


def test_equals_with_spaces_is_untouched():
    assert to_portable_markdown("a == b == c") == "a == b == c"


def test_multiline_color_span():
    assert to_portable_markdown('<span style="color:blue">1行目\n2行目</span>') == "1行目\n2行目"


def test_export_zip_notes_are_portable(client):
    import io
    import zipfile

    client.post("/api/notes", json={"title": "色", "body": '==蛍光== と <span style="color:red">赤</span>', "note_date": "2026-10-01"})
    z = zipfile.ZipFile(io.BytesIO(client.get("/api/export").content))
    md = next(n for n in z.namelist() if n.endswith(".md"))
    assert z.read(md).decode() == "# 色\n\n蛍光 と 赤\n"
    # data.json は復元用なので書いたとおりに残す
    assert "==蛍光==" in z.read("data.json").decode()
