"""A Lightkone library: the plain files the web app keeps in your storage.

    lightkone/library.json            every paper (the source of truth)
    lightkone/library.bib             the whole library as BibTeX, rewritten on every save
    lightkone/annotations/<id>.json   highlights and their notes
    lightkone/citations.json          the citation map's references from OpenAlex
    papers/All Papers/...             the PDFs, filed by first author like Paperpile

Papers are plain dicts in the shape of Lightkone's ``Paper`` type, so fields
this version does not know about survive a save untouched.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
import unicodedata
import uuid
from typing import Any, Callable, Iterable, Optional

from kirsche.lightkone.bibtex import library_to_bibtex
from kirsche.lightkone.merge import merge_libraries
from kirsche.lightkone.storage import Storage

LIBRARY_PATH = "lightkone/library.json"
BIB_PATH = "lightkone/library.bib"
PDF_DIR = "papers/"

Paper = dict  # a Lightkone paper record; see Lightkone's src/core/types.ts


def now_iso() -> str:
    """An ISO timestamp the way JavaScript's ``toISOString`` writes it."""
    t = _dt.datetime.now(_dt.timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


def norm_doi(d: Optional[str]) -> Optional[str]:
    if not d:
        return None
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", d.strip().lower()) or None


def norm_arxiv(a: Optional[str]) -> Optional[str]:
    if not a:
        return None
    return re.sub(r"v\d+$", "", re.sub(r"^arxiv:", "", a.strip().lower())) or None


def _norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", t.lower())


def make_key(d: dict, taken: set) -> str:
    """Paperpile-style citation key: Lastname + year + two letters from the title (e.g. Hinton2012-in)."""
    first = (d.get("authors") or ["Anon"])[0].split(",")[0]
    last = re.sub(r"[^A-Za-z]", "", unicodedata.normalize("NFKD", first)) or "Anon"
    words = [
        w for w in re.sub(r"[^a-z ]", "", d["title"].lower()).split(" ") if len(w) > 3
    ]
    base = f"{last[0].upper()}{last[1:]}{d.get('year') or ''}"
    w0 = words[0] if words else "xx"
    w1 = words[1] if len(words) > 1 else w0
    suffix = (w0[:1] + w1[:1]).ljust(2, "x")
    key = f"{base}-{suffix}"
    i = 2
    while key in taken:
        key = f"{base}-{suffix}{i}"
        i += 1
    return key


# --- filing, as in Lightkone's core/filing.ts and core/folders.ts ---


def _surname(a: str) -> str:
    return (a.split(",")[0] if "," in a else a).strip()


def _clean(s: str) -> str:
    s = s.replace("---", "—").replace("--", "–")
    s = re.sub(r'[:/\\?*"<>|]', " - ", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"( - )+", " - ", s)
    return re.sub(r"^[\s-]+|[\s-]+$", "", s)


def author_folder(author: str) -> str:
    """The folder Paperpile files an author's papers under: the surname in capitals."""
    return _clean(_surname(author)).upper()


def _author_part(authors: list, title: str) -> str:
    names = [n for n in (_surname(a) for a in authors) if n]
    if not names:
        s = title
    elif len(names) == 1:
        s = names[0]
    elif len(names) == 2:
        s = f"{names[0]} and {names[1]}"
    else:
        s = f"{names[0]} et al."
    return s[:37] + "..." if len(s) > 40 else s


def paperpile_file(p: dict) -> str:
    """Path under papers/, as in Paperpile's BibTeX ``file`` field."""
    authors = p.get("authors") or []
    first = author_folder(authors[0]) if authors else ""
    title = _clean(p.get("title", "")) or "Untitled"
    head = _clean(
        " ".join(str(x) for x in [_author_part(authors, title), p.get("year")] if x)
    )
    name = f"{head} - {title}"
    if len(name) > 146:
        name = f"{name[:72].rstrip()} ... {name[-69:].lstrip()}"
    return f"All Papers/{first or 'Other'}/{name}.pdf"


def folders_from_paperpile(file: Optional[str], authors: Optional[list] = None) -> list:
    names = {n for n in (author_folder(a) for a in (authors or [])) if n}

    def is_author_folder(d: str) -> bool:
        if d == "Other":
            return True
        return d in names if names else (d == d.upper() and d != d.lower())

    out: list = []
    for path in [s.strip() for s in (file or "").split(";") if s.strip()]:
        dirs = path.split("/")[:-1]
        if dirs and dirs[0] == "All Papers":
            dirs = dirs[1:]
        if not dirs or (len(dirs) == 1 and is_author_folder(dirs[0])):
            continue
        f = "/".join(dirs)
        if f not in out:
            out.append(f)
    return out


def clean_folder(f: str) -> str:
    return "/".join(s.strip() for s in f.split("/") if s.strip())


def _parse_file(raw: str) -> dict:
    f = json.loads(raw)
    if f.get("format") != "lightkone-library":
        raise ValueError(f"{LIBRARY_PATH} is not a Lightkone library.")
    if isinstance(f.get("version"), int) and f["version"] > 1:
        raise ValueError(
            f"{LIBRARY_PATH} was saved by a newer Lightkone (format version {f['version']}). Update kirsche to open it."
        )
    return f


def _dumps(file: dict) -> str:
    # The same text JavaScript's JSON.stringify(file, null, 1) gives, so an unchanged library is not rewritten.
    return json.dumps(file, indent=1, ensure_ascii=False)


class Library:
    """A Lightkone library in some storage.

    >>> lib = Library(FolderStorage("~/papers")).load()
    >>> lib.search("author:hinton year:2012")
    """

    def __init__(self, storage: Storage):
        self.storage = storage
        self.papers: list[Paper] = []
        self.bib_sync: list = []
        self._other: dict = {}
        self._base: Optional[str] = None

    # --- reading and saving ---

    def load(self) -> "Library":
        self.papers, self.bib_sync, self._other, self._base = [], [], {}, None
        raw = self.storage.read(LIBRARY_PATH)
        if raw is not None:
            self._base = raw.decode("utf-8")
            f = _parse_file(self._base)
            self._take(f)
        for p in self.papers:
            if "folders" not in p:
                p["folders"] = folders_from_paperpile(p.get("file"), p.get("authors"))
        return self

    def _take(self, f: dict) -> None:
        self.papers = f.get("papers", [])
        self.bib_sync = f.get("bibSync", [])
        self._other = {
            k: v
            for k, v in f.items()
            if k not in ("format", "version", "papers", "bibSync")
        }

    def _file(self) -> dict:
        out: dict = {"format": "lightkone-library", "version": 1, "papers": self.papers}
        if self.bib_sync:
            out["bibSync"] = self.bib_sync
        out.update(self._other)
        return out

    def _catch_up(self) -> int:
        raw = self.storage.read(LIBRARY_PATH)
        now = raw.decode("utf-8") if raw is not None else None
        if not now or now == self._base:
            return 0
        theirs = _parse_file(now)
        merged, from_them = merge_libraries(
            _parse_file(self._base) if self._base else None, self._file(), theirs
        )
        other = {
            k: v
            for k, v in theirs.items()
            if k not in ("format", "version", "papers", "bibSync")
        }
        self._take({**merged, **other})
        self._base = now
        return from_them

    def save(self) -> int:
        """Write library.json and library.bib, first merging in what was saved elsewhere.

        Returns how many papers took changes made elsewhere.
        """
        merged = self._catch_up()
        text = _dumps(self._file())
        if text == self._base:
            return merged
        self.storage.write(LIBRARY_PATH, text.encode("utf-8"), "application/json")
        self._base = text
        live = [p for p in self.papers if not p.get("trashed")]
        self.storage.write(
            BIB_PATH, library_to_bibtex(live).encode("utf-8"), "application/x-bibtex"
        )
        return merged

    def refresh(self) -> int:
        """Pick up changes saved elsewhere without writing."""
        return self._catch_up()

    # --- finding ---

    @property
    def live(self) -> list[Paper]:
        """Papers outside the trash."""
        return [p for p in self.papers if not p.get("trashed")]

    def search(self, query: str = "", sort: str = "added") -> list[Paper]:
        """Search with Lightkone's syntax: words, tag:, author:, year:2015-2020, in:, has:pdf, is:starred ..."""
        from kirsche.lightkone.query import search

        return search(self.papers, query, sort)

    def get(self, ref: str) -> Optional[Paper]:
        """A paper by citation key, id, DOI or arXiv id."""
        r = ref.strip()
        doi, arx = norm_doi(r), norm_arxiv(r)
        for p in self.papers:
            if p.get("key") == r or p.get("id") == r:
                return p
        for p in self.papers:
            if (doi and norm_doi(p.get("doi")) == doi) or (
                arx and norm_arxiv(p.get("arxiv")) == arx
            ):
                return p
        low = r.lower()
        for p in self.papers:
            if p.get("key", "").lower() == low:
                return p
        return None

    def find_duplicate(self, d: dict) -> Optional[Paper]:
        doi, arx, title = (
            norm_doi(d.get("doi")),
            norm_arxiv(d.get("arxiv")),
            _norm_title(d.get("title", "")),
        )
        for p in self.papers:
            if (
                (doi and norm_doi(p.get("doi")) == doi)
                or (arx and norm_arxiv(p.get("arxiv")) == arx)
                or (d.get("key") and p.get("key") == d.get("key"))
                or (len(title) > 20 and _norm_title(p.get("title", "")) == title)
            ):
                return p
        return None

    # --- changing ---

    def merge(self, drafts: Iterable[dict]) -> tuple[list[Paper], list[Paper]]:
        """Add drafts not already in the library; existing papers gain missing fields, tags and folders.

        Returns (added, updated).
        """
        added: list[Paper] = []
        updated: list[Paper] = []
        keys = {p.get("key") for p in self.papers}
        for d in drafts:
            if not (d.get("title") or "").strip():
                continue
            existing = self.find_duplicate(d)
            if existing is not None:
                changed = False
                for k in ("abstract", "doi", "arxiv", "url", "venue", "year", "file"):
                    if not existing.get(k) and d.get(k):
                        existing[k] = d[k]
                        changed = True
                tags = list(
                    dict.fromkeys([*existing.get("tags", []), *(d.get("tags") or [])])
                )
                if len(tags) != len(existing.get("tags", [])):
                    existing["tags"] = tags
                    changed = True
                new_folders = (
                    d["folders"]
                    if "folders" in d
                    else folders_from_paperpile(d.get("file"), d.get("authors"))
                )
                folders = list(
                    dict.fromkeys([*existing.get("folders", []), *new_folders])
                )
                if len(folders) != len(existing.get("folders", [])):
                    existing["folders"] = folders
                    changed = True
                if changed and existing not in updated:
                    updated.append(existing)
                continue
            key = (
                d["key"] if d.get("key") and d["key"] not in keys else make_key(d, keys)
            )
            keys.add(key)
            paper: Paper = {"type": "article", "authors": [], "fields": {}}
            paper.update(d)
            paper["tags"] = d.get("tags") or []
            paper["folders"] = (
                d["folders"]
                if "folders" in d
                else folders_from_paperpile(d.get("file"), d.get("authors"))
            )
            paper["id"] = str(uuid.uuid4())
            paper["key"] = key
            paper["added"] = d.get("added") or now_iso()
            self.papers.append(paper)
            added.append(paper)
        return added, updated

    def update(self, paper: Paper, **patch: Any) -> None:
        """Set fields on a paper; a value of None removes the field."""
        for k, v in patch.items():
            if k == "id":
                continue
            if v is None:
                paper.pop(k, None)
            else:
                paper[k] = v

    def remove(self, paper: Paper) -> None:
        """Delete a paper for good (its PDF stays in storage)."""
        self.papers = [p for p in self.papers if p.get("id") != paper.get("id")]

    def tag_counts(self) -> list[tuple[str, int]]:
        counts: dict[str, int] = {}
        for p in self.live:
            for t in p.get("tags", []):
                counts[t] = counts.get(t, 0) + 1
        return sorted(counts.items(), key=lambda kv: kv[0].lower())

    def folder_counts(self) -> list[tuple[str, int]]:
        """Every folder path and how many papers are in it or below it."""
        counts: dict[str, int] = {}
        for p in self.live:
            seen = set()
            for f in p.get("folders", []):
                parts = f.split("/")
                for i in range(1, len(parts) + 1):
                    path = "/".join(parts[:i])
                    if path not in seen:
                        seen.add(path)
                        counts[path] = counts.get(path, 0) + 1
        return sorted(counts.items(), key=lambda kv: kv[0].lower())

    def pdf_location(self, paper: Paper) -> tuple[str, str]:
        """Where a new PDF for this paper goes: (storage path, Paperpile ``file`` value)."""
        taken = set()
        for q in self.papers:
            if q.get("id") == paper.get("id"):
                continue
            if q.get("pdf"):
                taken.add(q["pdf"])
            for f in (q.get("file") or "").split(";"):
                taken.add(PDF_DIR + f.strip())
        file = paperpile_file(paper)
        candidate = file
        i = 2
        while PDF_DIR + candidate in taken:
            candidate = re.sub(r"\.pdf$", f" ({i}).pdf", file)
            i += 1
        return PDF_DIR + candidate, candidate

    # --- for notebooks ---

    def citations(self) -> dict:
        """The raw ``lightkone/citations.json``: per paper id, its OpenAlex id, year, citation count and references."""
        from kirsche.lightkone.citations import load_citations

        return load_citations(self)

    def citation_graph(
        self,
        query: str = "",
        fetch: bool = False,
        openalex_key: Optional[str] = None,
        min_missing: int = 2,
    ):
        """The citation map as a ``Graph`` (see ``to_dataframes``, ``to_networkx``, ``to_json``).

        With ``fetch=True`` references not yet known are fetched from OpenAlex
        first and kept in the library, as ``kirsche map`` does.
        """
        from kirsche.lightkone.citations import (
            OpenAlex,
            build_graph,
            fetch_citations,
            load_citations,
            needs_fetch,
            save_citations,
        )

        store = load_citations(self)
        if fetch and needs_fetch(self.papers, store):
            try:
                fetch_citations(self.papers, store, OpenAlex(openalex_key))
            finally:
                save_citations(self, store)
        g = build_graph(self.papers, store, min_missing)
        return g.subgraph(p["id"] for p in self.search(query)) if query else g

    def to_dataframe(
        self, papers: Optional[list[Paper]] = None, columns: Optional[list[str]] = None
    ):
        """The papers as a pandas DataFrame (pandas must be installed)."""
        import pandas as pd

        rows = papers if papers is not None else self.live
        df = pd.DataFrame(rows)
        if columns:
            df = df[[c for c in columns if c in df.columns]]
        return df


def edit(library: Library, change: Callable[[Library], Any]) -> Any:
    """Load, change and save in one go; returns what ``change`` returned."""
    library.load()
    result = change(library)
    library.save()
    return result
