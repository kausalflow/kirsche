"""BibTeX reading and writing, the same way Lightkone does it.

A forgiving reader (braces, quotes, nested braces, numbers, ``@string``
macros, month names and ``#`` concatenation) and the plain writer Lightkone
uses for ``lightkone/library.bib``. Kept in step with Lightkone's
``src/core/bibtex.ts`` so a library saved by either tool reads the same.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

MONTHS = {
    "jan": "January",
    "feb": "February",
    "mar": "March",
    "apr": "April",
    "may": "May",
    "jun": "June",
    "jul": "July",
    "aug": "August",
    "sep": "September",
    "oct": "October",
    "nov": "November",
    "dec": "December",
}


@dataclass
class BibEntry:
    type: str
    key: str
    fields: dict[str, str] = field(default_factory=dict)


_WORD_STOP = set(' \t\r\n,={}()"#')


def parse_bibtex(text: str) -> list[BibEntry]:
    """Every entry in a BibTeX text, with lower-cased field names and raw values."""
    entries: list[BibEntry] = []
    macros = dict(MONTHS)
    n = len(text)
    i = 0

    def skip_space() -> None:
        nonlocal i
        while i < n and text[i].isspace():
            i += 1

    def read_word() -> str:
        nonlocal i
        start = i
        while i < n and text[i] not in _WORD_STOP and not text[i].isspace():
            i += 1
        return text[start:i]

    def read_braced() -> str:
        nonlocal i
        depth = 0
        start = i + 1
        while i < n:
            c = text[i]
            if c == "\\":
                i += 2
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    i += 1
                    return text[start : i - 1]
            i += 1
        return text[start:]

    def read_quoted() -> str:
        nonlocal i
        depth = 0
        i += 1
        start = i
        while i < n:
            c = text[i]
            if c == "\\":
                i += 2
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            elif c == '"' and depth == 0:
                i += 1
                return text[start : i - 1]
            i += 1
        return text[start:]

    def read_value() -> str:
        nonlocal i
        parts: list[str] = []
        while True:
            skip_space()
            c = text[i] if i < n else ""
            if c == "{":
                parts.append(read_braced())
            elif c == '"':
                parts.append(read_quoted())
            else:
                w = read_word()
                if not w:
                    break
                parts.append(w if w.isdigit() else macros.get(w.lower(), w))
            skip_space()
            if i < n and text[i] == "#":
                i += 1
                continue
            break
        return "".join(parts)

    while i < n:
        at = text.find("@", i)
        if at < 0:
            break
        i = at + 1
        typ = read_word().lower()
        skip_space()
        opening = text[i] if i < n else ""
        if opening not in ("{", "("):
            continue
        close = "}" if opening == "{" else ")"
        i += 1
        if typ == "comment":
            i = at + 1
            continue
        if typ == "preamble":
            read_value()
            continue
        if typ == "string":
            skip_space()
            name = read_word().lower()
            skip_space()
            if i < n and text[i] == "=":
                i += 1
                macros[name] = read_value()
            continue
        skip_space()
        key_start = i
        depth = 0
        # Braces in a key ("Erd\H{o}s1959") are part of it, not the end of the entry.
        while i < n and (depth > 0 or (text[i] != "," and text[i] != close)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        key = text[key_start:i].strip()
        fields: dict[str, str] = {}
        while i < n and text[i] != close:
            if text[i] == ",":
                i += 1
            skip_space()
            if i >= n or text[i] == close:
                break
            name = read_word().lower()
            skip_space()
            if not name or i >= n or text[i] != "=":
                # Malformed field: skip its values, then to the next comma or the end of the entry.
                while i < n and text[i] != "," and text[i] != close:
                    if text[i] == "{":
                        read_braced()
                    elif text[i] == '"':
                        read_quoted()
                    else:
                        i += 1
                continue
            i += 1
            fields[name] = re.sub(r"\s+", " ", read_value()).strip()
            skip_space()
        i += 1
        if key or fields:
            entries.append(BibEntry(typ, key, fields))
    return entries


_ACCENTS = {
    '"': "\u0308",
    "'": "\u0301",
    "`": "\u0300",
    "^": "\u0302",
    "~": "\u0303",
    "=": "\u0304",
    ".": "\u0307",
    "c": "\u0327",
    "v": "\u030c",
    "u": "\u0306",
    "H": "\u030b",
}
_LETTERS = {
    "ss": "ß",
    "o": "ø",
    "O": "Ø",
    "ae": "æ",
    "AE": "Æ",
    "l": "ł",
    "L": "Ł",
    "i": "ı",
}

_ACCENT_RE = re.compile(
    r"\{?\\([\"'`^~=.]|[cvuH](?=[\s{]))\s*\{?([A-Za-z]|\\[ij]\b)\}?\}?"
)
_LETTER_RE = re.compile(r"\{\\(ss|o|O|ae|AE|l|L|i)\}|\\(ss|o|O|ae|AE|l|L|i)\b ?")


def plain(value: str) -> str:
    """Remove protective braces and the most common LaTeX escapes, for display and search."""
    v = _ACCENT_RE.sub(
        lambda m: unicodedata.normalize(
            "NFC", m.group(2).replace("\\", "") + _ACCENTS[m.group(1)]
        ),
        value,
    )
    v = _LETTER_RE.sub(lambda m: _LETTERS[m.group(1) or m.group(2)], v)
    v = re.sub(r"\\(?:emph|textit|textbf|mathrm|textrm)\{([^{}]*)\}", r"\1", v)
    v = re.sub(r"\\([&%$#_{}])", r"\1", v)
    v = re.sub(r"(?<!\\)[{}]", "", v)
    v = v.replace("~", " ")
    return re.sub(r"\s+", " ", v).strip()


_ARXIV_IN_URL = re.compile(
    r"arxiv\.org/(?:abs|pdf|html)/([^\s?#]+?)(?:v\d+)?(?:\.pdf)?(?:[?#]|$)", re.I
)
_ID_KEYWORD = re.compile(r"^(doi|url|arxiv|isbn|issn|pmid|pmc):|https?://", re.I)


def split_authors(value: str) -> list[str]:
    """BibTeX ``author`` field to "Last, First" strings."""
    if not value.strip():
        return []
    out = []
    for raw in re.split(r"\s+and\s+", value, flags=re.I):
        raw = raw.strip()
        a = plain(raw)
        if not a:
            continue
        # "{LIGO Scientific Collaboration}" is a corporate name: never flip it.
        if "," in a or a.lower() == "others" or re.match(r"^\{.*\}$", raw, re.S):
            out.append(a)
            continue
        parts = a.split(" ")
        out.append(f"{parts[-1]}, {' '.join(parts[:-1])}" if len(parts) > 1 else a)
    return out


def entry_to_draft(entry: BibEntry) -> dict[str, Any]:
    """A BibTeX entry as a paper draft (a paper without id and added date)."""
    f = dict(entry.fields)

    def take(name: str) -> str | None:
        return f.pop(name, None)

    title = plain(take("title") or "")
    author = take("author")
    editor = take("editor")
    authors = split_authors(author if author is not None else (editor or ""))
    year_raw = take("year")
    m = re.search(r"\d{4}", year_raw or "")
    year = int(m.group(0)) if m else None
    journal = take("journal")
    booktitle = take("booktitle")
    venue = (
        plain(journal or "")
        or plain(booktitle or "")
        or plain(f.get("publisher") or "")
    )
    abstract = take("abstract")
    doi = take("doi")
    if doi:
        doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.I)
    url = take("url")
    eprint = take("eprint")
    arxivid = take("arxivid")
    prefix = (f.get("archiveprefix") or f.get("eprinttype") or "").lower()
    arxiv = arxivid or (eprint if prefix == "arxiv" else None)
    if not arxiv and url:
        mm = _ARXIV_IN_URL.search(url)
        arxiv = mm.group(1) if mm else None
    if not arxiv and eprint and re.match(r"^\d{4}\.\d{4,5}", eprint):
        arxiv = eprint
    if arxiv:
        for k in ("archiveprefix", "eprinttype", "primaryclass"):
            f.pop(k, None)
    elif eprint:
        f["eprint"] = eprint
    tags = [plain(t) for t in re.split(r"[;,]", take("keywords") or "")]
    tags = [t for t in tags if t and not _ID_KEYWORD.search(t)]
    file = take("file")
    annote = take("annote")
    note = take("note")
    notes = annote if annote is not None else note
    draft: dict[str, Any] = {
        "key": entry.key,
        "type": entry.type,
        "title": title,
        "authors": authors,
        "year": year,
        "venue": venue or None,
        "abstract": plain(abstract) if abstract else None,
        "doi": doi or None,
        "arxiv": (
            re.sub(r"v\d+$", "", re.sub(r"^arxiv:", "", arxiv, flags=re.I))
            if arxiv
            else None
        ),
        "url": url,
        "tags": tags,
        "file": file,
        "notes": notes,
        "fields": f,
    }
    return {k: v for k, v in draft.items() if v is not None}


def parse_bibtex_to_drafts(text: str) -> list[dict[str, Any]]:
    return [entry_to_draft(e) for e in parse_bibtex(text) if e.fields.get("title")]


def _escape(v: str) -> str:
    return re.sub(r"\\?([&%#])", r"\\\1", v)


def paper_to_bibtex(p: dict[str, Any]) -> str:
    """One paper as BibTeX, exactly as Lightkone writes it."""
    lines: list[tuple[str, str]] = []

    def add(name: str, value: Any) -> None:
        if value is not None and value != "":
            lines.append((name, str(value)))

    add("title", "{" + _escape(p.get("title", "")) + "}")
    add(
        "author",
        " and ".join(
            a if ("," in a or a == "others") else "{" + a + "}"
            for a in p.get("authors", [])
        ),
    )
    add("year", p.get("year"))
    fields = p.get("fields") or {}
    venue_field = (
        "booktitle" if p.get("type") in ("inproceedings", "incollection") else "journal"
    )
    if p.get("venue") and not fields.get(venue_field):
        add(venue_field, _escape(p["venue"]))
    add("doi", p.get("doi"))
    if p.get("arxiv"):
        add("eprint", p["arxiv"])
        add("archiveprefix", "arXiv")
    add("url", p.get("url"))
    add("abstract", _escape(p["abstract"]) if p.get("abstract") else None)
    if p.get("tags"):
        add("keywords", ";".join(p["tags"]))
    add("file", p.get("file"))
    for k, v in fields.items():
        if not k.startswith("lightkone-"):
            add(k, v)
    width = max(len(k) for k, _ in lines)
    body = ",\n".join(f"  {k.ljust(width)} = {{{v}}}" for k, v in lines)
    return f"@{p.get('type') or 'misc'}{{{p['key']},\n{body}\n}}\n"


def library_to_bibtex(papers: list[dict[str, Any]]) -> str:
    return "\n".join(paper_to_bibtex(p) for p in papers)
