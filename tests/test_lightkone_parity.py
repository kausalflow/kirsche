"""The CLI must read and write a library exactly as the Lightkone web app does.

tests/data/lightkone/golden.json holds outputs of Lightkone's own TypeScript
code (src/core/bibtex.ts, library.ts, search.ts, merge.ts, filing.ts,
folders.ts, citations.ts) for the same inputs.
"""

import json
from pathlib import Path

import pytest

from kirsche.lightkone.bibtex import (
    library_to_bibtex,
    parse_bibtex_to_drafts,
    plain,
    split_authors,
)
from kirsche.lightkone.citations import build_graph
from kirsche.lightkone.library import (
    _dumps,
    folders_from_paperpile,
    make_key,
    paperpile_file,
)
from kirsche.lightkone.merge import merge_libraries
from kirsche.lightkone.query import search

G = json.loads(
    (Path(__file__).parent / "data" / "lightkone" / "golden.json").read_text("utf-8")
)


def test_bibtex_drafts():
    assert parse_bibtex_to_drafts(G["bib"]) == G["drafts"]


def test_keys():
    taken: set = set()
    keys = []
    for d in G["drafts"]:
        k = make_key(d, taken)
        taken.add(k)
        keys.append(k)
    assert keys == G["keys"]
    taken = set()
    out = []
    for d in G["extra"]:
        k = make_key(d, taken)
        taken.add(k)
        out.append(k)
    assert out == G["extraKeys"]


def test_library_bib():
    assert library_to_bibtex(G["papers"]) == G["libraryBib"]


def test_library_json_text():
    file = {"format": "lightkone-library", "version": 1, "papers": G["papers"]}
    assert _dumps(file) == G["libraryJson"]


@pytest.mark.parametrize("case", sorted(G["searches"]))
def test_search(case):
    q, sort = case.rsplit("|", 1)
    assert [p["key"] for p in search(G["papers"], q, sort)] == G["searches"][case]


def test_merge():
    m = G["merge"]
    merged, _ = merge_libraries(m["base"], m["ours"], m["theirs"])
    assert merged == m["merged"]["file"]


def test_graph():
    g = build_graph(G["papers"], G["store"])
    assert [list(e) for e in g.edges] == G["graph"]["edges"]
    assert [{"oa": oa, "by": by} for oa, by in g.missing] == G["graph"]["missing"]
    assert g.known == G["graph"]["known"]
    nodes = [
        {
            "id": n.paper["id"],
            "year": n.year,
            "cited": n.cited,
            "cites": n.cites,
            "citedBy": n.cited_by,
        }
        for n in g.nodes.values()
    ]
    assert nodes == G["graph"]["nodes"]


def test_filing():
    extra = [
        {"authors": [], "title": "Untitled: a note/on things?"},
        {"authors": ["O'Neil, Cathy", "Doe, J"], "title": "Weapons", "year": 2016},
        {"authors": ["Smith, A"], "title": "x" * 200, "year": 2000},
    ]
    assert [paperpile_file(p) for p in G["papers"] + extra] == G["filing"]


def test_folders_from_paperpile():
    assert [folders_from_paperpile(f, a) for f, a in G["folderCases"]] == G["folders"]


def test_plain_and_authors():
    for raw, want in G["plains"]:
        assert plain(raw) == want, raw
    for raw, want in G["authors"]:
        assert split_authors(raw) == want
