"""Turn a DOI, an arXiv id or a link holding one into a paper draft.

The same free, open sources as Lightkone: Crossref for DOIs, Semantic Scholar
then OpenAlex for arXiv ids.
"""

from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import quote, unquote

import requests

from kirsche.lightkone.storage import get_politely

ARXIV_NEW = re.compile(
    r"(?:arxiv\.org/(?:abs|pdf|html)/|arxiv:\s*)?(\d{4}\.\d{4,5})(?:v\d+)?", re.I
)
ARXIV_OLD = re.compile(
    r"(?:arxiv\.org/(?:abs|pdf)/|arxiv:\s*)([a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?",
    re.I,
)
DOI = re.compile(r"(10\.\d{4,9}/[^\s\"<>]+)")


class LookupError_(RuntimeError):
    pass


def arxiv_id(text: str) -> Optional[str]:
    s = text.strip()
    m = ARXIV_NEW.search(s) or ARXIV_OLD.search(s)
    return m.group(1) if m else None


def year_of_arxiv_id(aid: str) -> Optional[int]:
    m = re.match(r"^(\d{2})(\d{2})\.", aid) or re.search(r"/(\d{2})(\d{2})\d{3}$", aid)
    if not m:
        return None
    yy = int(m.group(1))
    return 1900 + yy if yy >= 91 else 2000 + yy


def doi_of(text: str) -> Optional[str]:
    m = DOI.search(unquote(text.strip()))
    if not m:
        return None
    doi = re.sub(r"[.,;)\]]+$", "", m.group(1))
    doi = re.sub(r"/(full|abstract|pdf|epdf)$", "", doi, flags=re.I)
    return None if re.match(r"^10\.48550/arxiv\.", doi, re.I) else doi


def _strip_tags(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip() or None


def _get_json(url: str, session: Optional[requests.Session] = None) -> Optional[Any]:
    r = get_politely(session or requests, url, {"Accept": "application/json"})
    if r.status_code == 404:
        return None
    if not r.ok:
        raise LookupError_(f"{url.split('/')[2]} answered {r.status_code}")
    return r.json()


def inverted_to_text(index: Optional[dict]) -> Optional[str]:
    """OpenAlex stores abstracts as an inverted index; rebuild the text."""
    if not index:
        return None
    words: dict[int, str] = {}
    for w, positions in index.items():
        for p in positions:
            words[p] = w
    return " ".join(words[i] for i in sorted(words)).strip() or None


def flip(name: str) -> str:
    parts = str(name).strip().split(" ")
    return f"{parts[-1]}, {' '.join(parts[:-1])}" if len(parts) > 1 else str(name)


TYPES = {
    "journal-article": "article",
    "proceedings-article": "inproceedings",
    "book-chapter": "incollection",
    "book": "book",
    "monograph": "book",
    "posted-content": "misc",
    "dissertation": "phdthesis",
    "report": "techreport",
}


def crossref(doi: str, session: Optional[requests.Session] = None) -> Optional[dict]:
    data = _get_json(f"https://api.crossref.org/works/{quote(doi, safe='')}", session)
    w = (data or {}).get("message") or {}
    if not (w.get("title") or [None])[0]:
        return None
    issued = (
        (w.get("issued") or {}).get("date-parts")
        or (w.get("published") or {}).get("date-parts")
        or [[None]]
    )
    abstract = w.get("abstract")
    if abstract:
        abstract = re.sub(r"<jats:title>.*?</jats:title>", "", abstract, count=1)
    fields = {}
    for src, dst in (
        ("volume", "volume"),
        ("issue", "number"),
        ("page", "pages"),
        ("publisher", "publisher"),
    ):
        if w.get(src):
            fields[dst] = w[src]
    authors = []
    for a in w.get("author") or []:
        if a.get("family"):
            authors.append(a["family"] + (f", {a['given']}" if a.get("given") else ""))
        elif a.get("name"):
            authors.append(a["name"])
    draft = {
        "type": TYPES.get(w.get("type") or "", "misc"),
        "title": _strip_tags(w["title"][0]),
        "authors": authors,
        "year": issued[0][0] if issued and issued[0] else None,
        "venue": (w.get("container-title") or [None])[0] or w.get("publisher"),
        "abstract": _strip_tags(abstract),
        "doi": w.get("DOI"),
        "url": w.get("URL"),
        "fields": fields,
    }
    return {k: v for k, v in draft.items() if v is not None}


def arxiv(aid: str, session: Optional[requests.Session] = None) -> Optional[dict]:
    try:
        s2 = _get_json(
            f"https://api.semanticscholar.org/graph/v1/paper/arXiv:{aid}?fields=title,authors,year,abstract,venue,externalIds",
            session,
        )
        if s2 and s2.get("title"):
            doi = (s2.get("externalIds") or {}).get("DOI")
            draft = {
                "type": "article",
                "title": s2["title"],
                "authors": [flip(a.get("name", "")) for a in s2.get("authors") or []],
                "year": s2.get("year"),
                "venue": s2.get("venue") or "arXiv",
                "abstract": s2.get("abstract"),
                "arxiv": aid,
                "doi": doi if doi and not re.match(r"^10\.48550", doi, re.I) else None,
                "url": f"https://arxiv.org/abs/{aid}",
                "fields": {},
            }
            return {k: v for k, v in draft.items() if v is not None}
    except (LookupError_, requests.RequestException):
        pass  # rate limited or offline: try OpenAlex
    oa = _get_json(f"https://api.openalex.org/works/doi:10.48550/arXiv.{aid}", session)
    if not oa or not oa.get("title"):
        return None
    draft = {
        "type": "article",
        "title": oa["title"],
        "authors": [
            flip((a.get("author") or {}).get("display_name", ""))
            for a in oa.get("authorships") or []
        ],
        "year": year_of_arxiv_id(aid) or oa.get("publication_year"),
        "venue": "arXiv",
        "abstract": inverted_to_text(oa.get("abstract_inverted_index")),
        "arxiv": aid,
        "url": f"https://arxiv.org/abs/{aid}",
        "fields": {},
    }
    return {k: v for k, v in draft.items() if v is not None}


def resolve(text: str, session: Optional[requests.Session] = None) -> Optional[dict]:
    """A paper draft for a DOI, an arXiv id, or a link holding either. None when it is neither or unknown."""
    aid = arxiv_id(text)
    if aid:
        return arxiv(aid, session)
    doi = doi_of(text)
    if doi:
        return crossref(doi, session)
    return None
