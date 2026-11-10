"""Safe saves: a three-way merge of library files, as in Lightkone's ``src/core/merge.ts``.

Before writing ``library.json`` the library is read again. If the web app, MCP
or another run of the CLI saved in the meantime, both versions are merged
against the one both started from, paper by paper and field by field. Only
when both sides changed the same field differently does this side's edit win.
"""

from __future__ import annotations

import json
from typing import Any, Optional

SETS = {"tags", "folders"}


def canonical(v: Any) -> str:
    """JSON with sorted keys, so equal values compare equal whatever order their fields were set in."""
    if isinstance(v, list):
        return "[" + ",".join(canonical(x) for x in v) + "]"
    if isinstance(v, dict):
        return (
            "{"
            + ",".join(
                f"{json.dumps(k, ensure_ascii=False)}:{canonical(v[k])}"
                for k in sorted(v)
                if v[k] is not None
            )
            + "}"
        )
    return json.dumps(v, ensure_ascii=False)


def _same(a: Any, b: Any) -> bool:
    return canonical(a) == canonical(b)


def _merge_set(
    base: Optional[list], ours: Optional[list], theirs: Optional[list]
) -> list:
    base, ours, theirs = base or [], ours or [], theirs or []
    removed = {x for x in base if x not in ours} | {x for x in base if x not in theirs}
    out: list = []
    for x in [*ours, *theirs]:
        if x not in out and x not in removed:
            out.append(x)
    return out


def _merge_paper(b: dict, o: dict, t: dict) -> dict:
    out: dict = {}
    keys = list(dict.fromkeys([*o.keys(), *t.keys(), *b.keys()]))
    v: Any
    for k in keys:
        if k in SETS and (isinstance(o.get(k), list) or isinstance(t.get(k), list)):
            v = _merge_set(b.get(k), o.get(k), t.get(k))
        else:
            v = t.get(k) if _same(o.get(k), b.get(k)) else o.get(k)
        if v is not None:
            out[k] = v
    return out


def merge_libraries(base: Optional[dict], ours: dict, theirs: dict) -> tuple[dict, int]:
    """Merge library files. Returns the merged file and how many papers took a change made elsewhere.

    ``base`` is the version this side last read or wrote (None when it had none),
    ``ours`` what it holds now, ``theirs`` what is in storage now.
    """
    base_by = {p["id"]: p for p in (base or {}).get("papers", [])}
    ours_by = {p["id"]: p for p in ours["papers"]}
    theirs_by = {p["id"]: p for p in theirs["papers"]}
    papers: list = []
    from_them = 0

    def pick(pid: str) -> Optional[dict]:
        b, o, t = base_by.get(pid), ours_by.get(pid), theirs_by.get(pid)
        if b is None:
            return o if o is not None else t
        if o is None:
            return t if t is not None and not _same(t, b) else None
        if t is None:
            return None if _same(o, b) else o
        if _same(o, b):
            return t
        if _same(t, b):
            return o
        return _merge_paper(b, o, t)

    for pid in dict.fromkeys([*theirs_by.keys(), *ours_by.keys()]):
        p = pick(pid)
        if p is not None:
            papers.append(p)
        if not _same(p, ours_by.get(pid)):
            from_them += 1

    bib_sync = (
        theirs.get("bibSync")
        if _same(ours.get("bibSync") or [], (base or {}).get("bibSync") or [])
        else ours.get("bibSync")
    )
    out: dict = {"format": "lightkone-library", "version": 1, "papers": papers}
    if bib_sync:
        out["bibSync"] = bib_sync
    return out, from_them
