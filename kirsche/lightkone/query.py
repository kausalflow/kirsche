"""Search with the same syntax as Lightkone's search box (``src/core/search.ts``).

Every word must match somewhere; title and author hits rank higher. Filters::

    tag:"machine learning"  author:hinton  year:2019  year:2015-2020
    in:"Physics/QFT"  is:starred  is:recent  is:trash
    has:pdf  has:abstract  has:arxiv  has:notes   no:pdf  no:abstract ...

Papers in the trash only show with ``is:trash``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional


def fold(s: str) -> str:
    return re.sub(r"[̀-ͯ]", "", unicodedata.normalize("NFKD", s)).lower()


@dataclass
class Query:
    words: list = field(default_factory=list)
    tags: list = field(default_factory=list)
    authors: list = field(default_factory=list)
    years: Optional[tuple] = None
    has: list = field(default_factory=list)
    no: list = field(default_factory=list)
    folders: list = field(default_factory=list)
    is_: list = field(default_factory=list)


_TOKEN = re.compile(r'(\w+):"([^"]*)"|(\w+):(\S+)|"([^"]*)"|(\S+)')


def parse_query(text: str) -> Query:
    q = Query()
    for m in _TOKEN.finditer(text):
        name = (m.group(1) or m.group(3) or "").lower() or None
        value = m.group(2) if m.group(2) is not None else m.group(4)
        if name == "tag":
            q.tags.append(fold(value))
        elif name == "author":
            q.authors.append(fold(value))
        elif name == "has":
            q.has.append(value.lower())
        elif name == "no":
            q.no.append(value.lower())
        elif name == "in":
            q.folders.append(fold(value).rstrip("/"))
        elif name == "is":
            q.is_.append(value.lower())
        elif name == "year":
            parts = value.split("-")
            try:
                a = int(parts[0])
                b = int(parts[1]) if len(parts) > 1 and parts[1] else a
                q.years = (a, b)
            except ValueError:
                pass
        else:
            w = (
                m.group(5)
                if m.group(5) is not None
                else (m.group(6) if m.group(6) is not None else m.group(0))
            )
            q.words.append(fold(w))
    return q


def _in_folder(p: dict, f: str) -> bool:
    return any(
        fold(pf) == f or fold(pf).startswith(f + "/") for pf in p.get("folders") or []
    )


def score(p: dict, q: Query) -> float:
    if bool(p.get("trashed")) != ("trash" in q.is_):
        return 0
    if "starred" in q.is_ and not p.get("starred"):
        return 0
    if "recent" in q.is_ and not p.get("opened"):
        return 0
    if q.folders and not all(_in_folder(p, f) for f in q.folders):
        return 0
    tags = p.get("tags") or []
    if q.tags and not all(any(fold(pt) == t for pt in tags) for t in q.tags):
        return 0
    author_text = fold(" ; ".join(p.get("authors") or []))
    if q.authors and not all(a in author_text for a in q.authors):
        return 0
    if q.years and (
        not p.get("year") or p["year"] < q.years[0] or p["year"] > q.years[1]
    ):
        return 0
    for h in q.has:
        if h == "pdf" and not p.get("pdf") and not p.get("file"):
            return 0
        if h in ("abstract", "arxiv", "notes") and not p.get(h):
            return 0
    for n in q.no:
        if n in ("pdf", "abstract", "arxiv", "notes") and p.get(n):
            return 0
    if not q.words:
        return 1
    title = fold(p.get("title", ""))
    rest = fold(
        " ".join(
            str(x)
            for x in [
                p.get("abstract"),
                p.get("venue"),
                " ".join(tags),
                p.get("key"),
                p.get("doi"),
                p.get("arxiv"),
                p.get("notes"),
            ]
            if x
        )
    )
    total = 0.0
    for w in q.words:
        s = (
            (5 if w in title else 0)
            + (4 if w in author_text else 0)
            + (1 if w in rest else 0)
        )
        if not s:
            return 0
        total += s
    return total


SORTS = ("added", "year", "title", "relevance", "opened")


def search(papers: list, text: str = "", sort: str = "added") -> list:
    q = parse_query(text)
    scored = [(p, s) for p in papers if (s := score(p, q)) > 0]
    if sort == "added" and "recent" in q.is_:
        sort = "opened"
    elif sort == "added" and q.words:
        sort = "relevance"
    if sort == "relevance":
        scored.sort(key=lambda x: x[0].get("added", ""), reverse=True)
        scored.sort(key=lambda x: x[1], reverse=True)
    elif sort == "year":
        scored.sort(key=lambda x: x[0].get("year") or 0, reverse=True)
    elif sort == "title":
        scored.sort(key=lambda x: x[0].get("title", "").lower())
    elif sort == "opened":
        scored.sort(
            key=lambda x: (x[0].get("opened") or "", x[0].get("added", "")),
            reverse=True,
        )
    else:
        scored.sort(key=lambda x: x[0].get("added", ""), reverse=True)
    return [p for p, _ in scored]
