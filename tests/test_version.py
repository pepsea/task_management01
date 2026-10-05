from app.version import read_version


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def test_reads_loose_ref_and_build_time(tmp_path):
    write(tmp_path / ".git/HEAD", "ref: refs/heads/main\n")
    write(tmp_path / ".git/refs/heads/main", "652cd62aaaabbbbccccddddeeeeffff00001111\n")
    write(tmp_path / "BUILD_TIME", "2026-10-06 10:00\n")
    assert read_version(tmp_path) == {"commit": "652cd62", "built_at": "2026-10-06 10:00"}


def test_falls_back_to_packed_refs(tmp_path):
    write(tmp_path / ".git/HEAD", "ref: refs/heads/main\n")
    write(tmp_path / ".git/packed-refs",
          "# pack-refs with: peeled fully-peeled sorted\nd98002a2f997d4882805a577ee9e1e7256fa1929 refs/heads/main\n")
    assert read_version(tmp_path) == {"commit": "d98002a", "built_at": None}


def test_detached_head(tmp_path):
    write(tmp_path / ".git/HEAD", "1234567890abcdef1234567890abcdef12345678\n")
    assert read_version(tmp_path)["commit"] == "1234567"


def test_no_git(tmp_path):
    assert read_version(tmp_path) == {"commit": None, "built_at": None}


def test_version_endpoint(client):
    r = client.get("/api/version")
    assert r.status_code == 200
    assert set(r.json()) == {"commit", "built_at"}
