import datetime as dt
import json

import pytest
from typer.testing import CliRunner

from kirsche.cli import app
from kirsche.lightkone.library import BIB_PATH, LIBRARY_PATH, Library
from kirsche.lightkone.storage import FolderStorage, GitHubStorage, S3Storage

BIB = """
@article{Abbott2016-ob,
  title = {Observation of Gravitational Waves from a Binary Black Hole Merger},
  author = {Abbott, B. P. and Thorne, Kip S.},
  journal = {Physical Review Letters}, year = 2016,
  doi = {10.1103/PhysRevLett.116.061102},
  keywords = {gravitational waves}
}
@misc{hu2021lora,
  title = {LoRA: Low-Rank Adaptation of Large Language Models},
  author = {Hu, Edward J. and Shen, Yelong},
  year = 2021, eprint = {2106.09685}, archivePrefix = {arXiv}
}
"""


@pytest.fixture
def lib_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("KIRSCHE_CONFIG", str(tmp_path / "config.json"))
    monkeypatch.delenv("LIGHTKONE_DIR", raising=False)
    monkeypatch.delenv("LIGHTKONE_LIBRARY", raising=False)
    d = tmp_path / "lib"
    d.mkdir()
    (tmp_path / "refs.bib").write_text(BIB)
    return d


def run(*args, input=None):
    r = CliRunner().invoke(app, list(args), input=input, catch_exceptions=False)
    return r


def test_import_list_tag_note_export(lib_dir, tmp_path):
    r = run(
        "--dir", str(lib_dir), "import", str(tmp_path / "refs.bib"), "-f", "Physics/GR"
    )
    assert "2 new" in r.output
    data = json.loads((lib_dir / LIBRARY_PATH).read_text())
    assert data["format"] == "lightkone-library" and len(data["papers"]) == 2
    assert (lib_dir / BIB_PATH).exists()

    r = run("--dir", str(lib_dir), "ls", "-o", "keys")
    assert set(r.output.split()) == {"Abbott2016-ob", "hu2021lora"}
    r = run("--dir", str(lib_dir), "ls", "author:abbott", "-o", "keys")
    assert r.output.split() == ["Abbott2016-ob"]

    run("--dir", str(lib_dir), "tag", "hu2021lora", "-a", "ml", "-a", "lora")
    run("--dir", str(lib_dir), "tag", "-q", "tag:ml", "-r", "lora")
    run("--dir", str(lib_dir), "note", "2106.09685", "Low-rank", "updates.")
    run("--dir", str(lib_dir), "star", "Abbott2016-ob")
    p = Library(FolderStorage(lib_dir)).load().get("hu2021lora")
    assert (
        p["tags"] == ["ml"]
        and p["notes"] == "Low-rank updates."
        and p["folders"] == ["Physics/GR"]
    )

    r = run("--dir", str(lib_dir), "ls", "is:starred", "-o", "keys")
    assert r.output.split() == ["Abbott2016-ob"]
    r = run("--dir", str(lib_dir), "export", "tag:ml")
    assert r.output.startswith("@misc{hu2021lora,")
    r = run("--dir", str(lib_dir), "show", "hu2021lora")
    assert "LoRA" in r.output and "Physics/GR" in r.output

    run("--dir", str(lib_dir), "trash", "hu2021lora")
    assert run("--dir", str(lib_dir), "ls", "-o", "keys").output.split() == [
        "Abbott2016-ob"
    ]
    assert "hu2021lora" not in (lib_dir / BIB_PATH).read_text()
    run("--dir", str(lib_dir), "trash", "-q", "is:trash", "--restore")
    assert len(run("--dir", str(lib_dir), "ls", "-o", "keys").output.split()) == 2

    r = run("--dir", str(lib_dir), "folders")
    assert "Physics" in r.output and "GR" in r.output


def test_unknown_paper(lib_dir):
    r = CliRunner().invoke(app, ["--dir", str(lib_dir), "show", "Nope2000-xx"])
    assert r.exit_code == 1 and "No paper" in r.output


def test_login_folder_and_default(lib_dir, tmp_path):
    r = run("login", "home", "--provider", "folder", "--set", f"path={lib_dir}")
    assert "Library 'home'" in r.output
    assert "* home" in run("libraries").output
    run("import", str(tmp_path / "refs.bib"))
    assert len(run("ls", "-o", "keys").output.split()) == 2
    config = (tmp_path / "config.json").stat().st_mode & 0o777
    assert config == 0o600


def test_login_from_backup(lib_dir, tmp_path):
    backup = {
        "format": "lightkone-settings",
        "version": 1,
        "exported": "2026-11-10T00:00:00.000Z",
        "settings": {
            "storage.provider": "folder",
            "storage.folder.path": str(lib_dir),
            "claude.key": "sk-secret",
            "related.openalexKey": "oa",
        },
    }
    f = tmp_path / "backup.json"
    f.write_text(json.dumps(backup))
    run("login", "--from-backup", str(f))
    saved = json.loads((tmp_path / "config.json").read_text())
    assert saved["libraries"]["main"] == {
        "storage.provider": "folder",
        "storage.folder.path": str(lib_dir),
        "related.openalexKey": "oa",
    }


def test_encrypted_backup(tmp_path):
    # Made the way Lightkone's exportSettings does: PBKDF2-SHA-256 then AES-GCM.
    import base64
    import os

    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    from kirsche.lightkone.settings import read_backup

    salt, iv = os.urandom(16), os.urandom(12)
    key = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=salt, iterations=1000
    ).derive(b"pw")
    data = AESGCM(key).encrypt(
        iv, json.dumps({"storage.provider": "s3"}).encode(), None
    )
    b64 = lambda x: base64.b64encode(x).decode()
    text = json.dumps(
        {
            "format": "lightkone-settings",
            "version": 1,
            "encrypted": {
                "salt": b64(salt),
                "iv": b64(iv),
                "data": b64(data),
                "iterations": 1000,
            },
        }
    )
    assert read_backup(text, "pw") == {"storage.provider": "s3"}
    with pytest.raises(ValueError, match="Wrong passphrase"):
        read_backup(text, "nope")


def test_save_merges_changes_made_elsewhere(lib_dir, tmp_path):
    run("--dir", str(lib_dir), "import", str(tmp_path / "refs.bib"))
    mine = Library(FolderStorage(lib_dir)).load()
    other = Library(FolderStorage(lib_dir)).load()
    other.get("hu2021lora")["tags"] = ["from-the-app"]
    other.save()
    mine.get("Abbott2016-ob")["starred"] = True
    assert mine.save() == 1
    fresh = Library(FolderStorage(lib_dir)).load()
    assert fresh.get("hu2021lora")["tags"] == ["from-the-app"]
    assert fresh.get("Abbott2016-ob")["starred"] is True


def test_unchanged_library_is_not_rewritten(lib_dir, tmp_path):
    run("--dir", str(lib_dir), "import", str(tmp_path / "refs.bib"))
    before = (lib_dir / LIBRARY_PATH).stat().st_mtime_ns
    lib = Library(FolderStorage(lib_dir)).load()
    lib.save()
    assert (lib_dir / LIBRARY_PATH).stat().st_mtime_ns == before


def test_attach_and_pdf(lib_dir, tmp_path, monkeypatch):
    run("--dir", str(lib_dir), "import", str(tmp_path / "refs.bib"))
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1.4 hello")
    r = run("--dir", str(lib_dir), "attach", "Abbott2016-ob", str(pdf))
    assert (
        "papers/All Papers/ABBOTT/Abbott and Thorne 2016 - Observation of Gravitational Waves"
        in r.output
    )
    out = tmp_path / "out.pdf"
    run("--dir", str(lib_dir), "pdf", "Abbott2016-ob", "-o", str(out))
    assert out.read_bytes() == b"%PDF-1.4 hello"


def test_map_offline(lib_dir, tmp_path):
    run("--dir", str(lib_dir), "import", str(tmp_path / "refs.bib"))
    lib = Library(FolderStorage(lib_dir)).load()
    a, h = lib.get("Abbott2016-ob"), lib.get("hu2021lora")
    store = {
        "format": "lightkone-citations",
        "version": 1,
        "works": {
            a["id"]: {
                "oa": "W1",
                "year": 2016,
                "cited": 9000,
                "refs": ["W7"],
                "at": "2026-01-01T00:00:00.000Z",
            },
            h["id"]: {
                "oa": "W2",
                "year": 2021,
                "cited": 500,
                "refs": ["W1", "W7"],
                "at": "2026-01-01T00:00:00.000Z",
            },
        },
    }
    (lib_dir / "lightkone" / "citations.json").write_text(json.dumps(store))
    out = tmp_path / "map.json"
    r = run("--dir", str(lib_dir), "map", "--no-fetch", "-o", str(out))
    assert "2 papers" in r.output and "1 link" in r.output
    g = json.loads(out.read_text())
    assert g["edges"] == [{"source": h["id"], "target": a["id"]}]
    html = tmp_path / "map.html"
    run("--dir", str(lib_dir), "map", "--no-fetch", "-o", str(html))
    page = html.read_text()
    assert (
        page.startswith("<!doctype html>")
        and "<script src" not in page
        and "LoRA" in page
    )


def test_s3_signature_matches_aws_example():
    # AWS's documented GET Object example for Signature Version 4.
    s = S3Storage(
        "https://examplebucket.s3.amazonaws.com",
        "examplebucket",
        "AKIAIOSFODNN7EXAMPLE",
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        region="us-east-1",
    )
    h = s.signed_headers(
        "GET",
        "/test.txt",
        {},
        b"",
        now=dt.datetime(2013, 5, 24, tzinfo=dt.timezone.utc),
        extra={"range": "bytes=0-9"},
    )
    assert h["authorization"].endswith(
        "Signature=f0e8bdb87c964420e857bd35b5d6ed310bd44f0170aba48dd91039c6036bdb41"
    )
    assert (
        "SignedHeaders=host;range;x-amz-content-sha256;x-amz-date" in h["authorization"]
    )


class FakeResponse:
    def __init__(self, status, body=b"", js=None):
        self.status_code = status
        self.content = body
        self.text = body.decode() if isinstance(body, bytes) else body
        self._js = js
        self.ok = 200 <= status < 300

    def json(self):
        return self._js


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.calls = []

    def request(self, method, url, data=None, headers=None, timeout=None):
        self.calls.append((method, url, headers))
        path = url.split("?")[0].split("/papers/", 1)[-1] if "/papers/" in url else ""
        from urllib.parse import unquote

        path = unquote(path)
        if method == "PUT":
            self.objects[path] = data
            return FakeResponse(200)
        if method == "GET" and "list-type=2" in url:
            keys = "".join(
                f"<Contents><Key>{k}</Key></Contents>" for k in sorted(self.objects)
            )
            return FakeResponse(
                200,
                f"<ListBucketResult><IsTruncated>false</IsTruncated>{keys}</ListBucketResult>".encode(),
            )
        if method == "GET":
            return (
                FakeResponse(200, self.objects[path])
                if path in self.objects
                else FakeResponse(404)
            )
        return FakeResponse(204)


def test_s3_storage_round_trip():
    fake = FakeS3()
    s = S3Storage(
        "https://acct.r2.cloudflarestorage.com",
        "papers",
        "id",
        "secret",
        prefix="lab",
        session=fake,
    )
    s.write("papers/All Papers/A B.pdf", b"%PDF", "application/pdf")
    assert fake.objects == {"lab/papers/All Papers/A B.pdf": b"%PDF"}
    assert "/papers/lab/papers/All%20Papers/A%20B.pdf" in fake.calls[0][1]
    assert s.read("papers/All Papers/A B.pdf") == b"%PDF"
    assert s.read("missing") is None
    assert s.list("papers/") == ["papers/All Papers/A B.pdf"]


class FakeGitHub:
    def __init__(self):
        self.files = {}

    def get(self, url, params=None, headers=None, timeout=None):
        if "/git/trees/" in url:
            return FakeResponse(
                200, js={"tree": [{"path": p, "type": "blob"} for p in self.files]}
            )
        path = url.split("/contents/", 1)[1].replace("%2F", "/")
        if path not in self.files:
            return FakeResponse(404)
        if "raw" in headers["Accept"]:
            return FakeResponse(200, self.files[path])
        return FakeResponse(200, js={"sha": "sha-" + path})

    def put(self, url, json=None, headers=None, timeout=None):
        import base64

        path = url.split("/contents/", 1)[1]
        self.files[path] = base64.b64decode(json["content"])
        self.last = json
        return FakeResponse(201, js={})

    def delete(self, url, json=None, headers=None, timeout=None):
        self.files.pop(url.split("/contents/", 1)[1], None)
        return FakeResponse(200, js={})


def test_github_storage_library_round_trip():
    fake = FakeGitHub()
    s = GitHubStorage("me/papers", "tok", branch="main", session=fake)
    lib = Library(s).load()
    lib.merge(
        [{"title": "A paper on lensing", "authors": ["Einstein, Albert"], "year": 1936}]
    )
    lib.save()
    assert (
        "lightkone/library.json" in fake.files and "lightkone/library.bib" in fake.files
    )
    assert fake.last["branch"] == "main"
    again = Library(s).load()
    assert again.papers[0]["key"] == "Einstein1936-pl"
    assert s.list("lightkone/") == ["lightkone/library.json", "lightkone/library.bib"]


def test_open_in_web_app(lib_dir, tmp_path):
    run("--dir", str(lib_dir), "import", str(tmp_path / "refs.bib"))
    pid = Library(FolderStorage(lib_dir)).load().get("hu2021lora")["id"]
    r = run("--dir", str(lib_dir), "open", "hu2021lora", "-p", "3", "--print")
    assert (
        r.output.strip()
        == f"https://lightkone.lab.kausalflow.com/app/?open={pid}&page=3"
    )
    r = run("web", "--print", "--url", "https://staging.lightkone.pages.dev/app/?x=1#y")
    assert r.output.strip() == "https://staging.lightkone.pages.dev/app/"


def _demo_graph(lib_dir, tmp_path):
    run("--dir", str(lib_dir), "import", str(tmp_path / "refs.bib"))
    lib = Library(FolderStorage(lib_dir)).load()
    a, h = lib.get("Abbott2016-ob"), lib.get("hu2021lora")
    store = {
        "format": "lightkone-citations",
        "version": 1,
        "works": {
            a["id"]: {
                "oa": "W1",
                "year": 2016,
                "cited": 9000,
                "refs": ["W7"],
                "at": "2026-01-01T00:00:00.000Z",
            },
            h["id"]: {
                "oa": "W2",
                "year": 2021,
                "cited": 500,
                "refs": ["W1", "W7"],
                "at": "2026-01-01T00:00:00.000Z",
            },
        },
    }
    (lib_dir / "lightkone" / "citations.json").write_text(json.dumps(store))
    return lib, a, h


def test_raw_data_api(lib_dir, tmp_path):
    lib, a, h = _demo_graph(lib_dir, tmp_path)
    assert lib.citations()["works"][a["id"]]["oa"] == "W1"
    g = lib.citation_graph()
    nodes, edges = g.to_dataframes()
    assert set(nodes["key"]) == {"Abbott2016-ob", "hu2021lora"}
    assert edges.to_dict("records") == [{"source": h["id"], "target": a["id"]}]
    assert g.missing == [("W7", [a["id"], h["id"]])]
    nxg = g.to_networkx()
    assert (
        list(nxg.edges) == [(h["id"], a["id"])] and nxg.nodes[a["id"]]["cited"] == 9000
    )
    only = lib.citation_graph("author:hu")
    assert list(only.nodes) == [h["id"]] and only.edges == []
    assert set(lib.to_dataframe()["key"]) == {"Abbott2016-ob", "hu2021lora"}


def test_map_exports(lib_dir, tmp_path):
    _demo_graph(lib_dir, tmp_path)
    for name in ("m.graphml", "m.gexf", "m.csv"):
        run("--dir", str(lib_dir), "map", "--no-fetch", "-o", str(tmp_path / name))
        assert (tmp_path / name).stat().st_size > 0
    assert (tmp_path / "m-edges.csv").read_text().splitlines()[0] == "source,target"
