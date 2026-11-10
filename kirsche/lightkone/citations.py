"""The citation map: which papers in a library cite which, and what they keep citing that it lacks.

References come from OpenAlex and are kept in ``lightkone/citations.json``,
the same file the Lightkone web app's Citation map reads and writes, so a
paper fetched by either tool is not fetched again by the other.
"""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional
from urllib.parse import quote

import requests

from kirsche.lightkone.library import Library, Paper, now_iso
from kirsche.lightkone.lookup import flip
from kirsche.lightkone.storage import get_politely

CITATIONS_PATH = "lightkone/citations.json"
API = "https://api.openalex.org/works"
BATCH = 50
#: Papers OpenAlex did not know are asked about again after this long.
RETRY_SECONDS = 30 * 24 * 3600


def empty_store() -> dict:
    return {"format": "lightkone-citations", "version": 1, "works": {}}


def load_citations(library: Library) -> dict:
    raw = library.storage.read(CITATIONS_PATH)
    if not raw:
        return empty_store()
    try:
        s = json.loads(raw.decode("utf-8"))
    except ValueError:
        return empty_store()
    return s if s.get("format") == "lightkone-citations" else empty_store()


def save_citations(library: Library, store: dict) -> None:
    text = json.dumps(store, ensure_ascii=False, separators=(",", ":"))
    library.storage.write(CITATIONS_PATH, text.encode("utf-8"), "application/json")


def _short(url: str) -> str:
    return url[url.rfind("/") + 1 :]


def doi_for_openalex(p: Paper) -> Optional[str]:
    """The DOI OpenAlex files a paper under: its own, or arXiv's for a preprint."""
    if p.get("doi"):
        return re.sub(r"^https?://(dx\.)?doi\.org/", "", p["doi"].lower())
    if p.get("arxiv"):
        a = re.sub(r"v\d+$", "", re.sub(r"^arxiv:", "", p["arxiv"].lower()))
        return f"10.48550/arxiv.{a}"
    return None


def _parse_iso(s: str) -> float:
    import datetime as _dt

    return _dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def needs_fetch(papers: list, store: dict, now: Optional[float] = None) -> list:
    """Papers to look up: never fetched, or not found a while ago."""
    now = now if now is not None else time.time()
    out = []
    for p in papers:
        if p.get("trashed") or not doi_for_openalex(p):
            continue
        w = store["works"].get(p["id"])
        if not w or (not w.get("oa") and now - _parse_iso(w["at"]) > RETRY_SECONDS):
            out.append(p)
    return out


class OpenAlex:
    def __init__(
        self, key: Optional[str] = None, session: Optional[requests.Session] = None
    ):
        self.key = key
        self.http = session or requests.Session()

    def get(self, url: str) -> dict:
        if self.key:
            url += f"&api_key={quote(self.key, safe='')}"
        r = get_politely(self.http, url)
        if r.status_code == 429:
            raise RuntimeError(
                "OpenAlex's free daily budget for your network is used up. "
                "Pass an OpenAlex key (--openalex-key or OPENALEX_API_KEY), or try again tomorrow."
            )
        if not r.ok:
            raise RuntimeError(f"OpenAlex answered {r.status_code}.")
        return r.json()


def fetch_citations(
    papers: list,
    store: dict,
    oa: OpenAlex,
    progress: Optional[Callable[[int, int], None]] = None,
) -> int:
    """Fetch references for papers not yet in the store, 50 at a time. Returns how many were found."""
    todo = needs_fetch(papers, store)
    found = 0
    for i in range(0, len(todo), BATCH):
        batch = todo[i : i + BATCH]
        by_doi = {doi_for_openalex(p) or "": p for p in batch}
        filt = "|".join(re.sub(r"[|,]", "", d) for d in by_doi)
        data = oa.get(
            f"{API}?filter=doi:{quote(filt, safe='')}&per-page={BATCH}&select=id,doi,publication_year,cited_by_count,referenced_works"
        )
        at = now_iso()
        for p in batch:
            store["works"][p["id"]] = {"oa": None, "refs": [], "at": at}
        for w in data.get("results") or []:
            p = by_doi.get(
                re.sub(r"^https://doi\.org/", "", str(w.get("doi") or "").lower())
            )
            if not p:
                continue
            work: dict = {"oa": _short(w["id"])}
            if w.get("publication_year"):
                work["year"] = w["publication_year"]
            work["cited"] = w.get("cited_by_count") or 0
            work["refs"] = [_short(r) for r in w.get("referenced_works") or []]
            work["at"] = at
            store["works"][p["id"]] = work
            found += 1
        if progress:
            progress(min(i + BATCH, len(todo)), len(todo))
    return found


@dataclass
class Node:
    paper: Paper
    year: int
    cited: int
    cites: list = field(default_factory=list)
    cited_by: list = field(default_factory=list)


@dataclass
class Graph:
    nodes: dict
    edges: list
    #: Works cited by several library papers that the library lacks: (OpenAlex id, [citing paper ids]).
    missing: list
    #: Papers that have references from OpenAlex.
    known: int


def build_graph(papers: list, store: dict, min_missing: int = 2) -> Graph:
    live = [p for p in papers if not p.get("trashed")]
    works = store["works"]
    by_oa = {
        works[p["id"]]["oa"]: p["id"]
        for p in live
        if (works.get(p["id"]) or {}).get("oa")
    }
    nodes = {}
    for p in live:
        w = works.get(p["id"]) or {}
        nodes[p["id"]] = Node(
            p, p.get("year") or w.get("year") or 0, w.get("cited") or 0
        )
    edges = []
    counts: dict = {}
    known = 0
    for p in live:
        w = works.get(p["id"]) or {}
        if not w.get("oa"):
            continue
        known += 1
        for r in dict.fromkeys(w.get("refs") or []):
            target = by_oa.get(r)
            if target and target != p["id"]:
                edges.append((p["id"], target))
                nodes[p["id"]].cites.append(target)
                nodes[target].cited_by.append(p["id"])
            elif not target:
                counts.setdefault(r, []).append(p["id"])
    missing = sorted(
        ((oa, by) for oa, by in counts.items() if len(by) >= min_missing),
        key=lambda x: (-len(x[1]), x[0]),
    )
    return Graph(nodes, edges, missing, known)


def works_by_id(ids: list, oa: OpenAlex) -> dict:
    """Paper drafts for works by OpenAlex id, with ``cited`` counts."""
    out = {}
    for i in range(0, len(ids), BATCH):
        batch = ids[i : i + BATCH]
        data = oa.get(
            f"{API}?filter=openalex:{'|'.join(batch)}&per-page={BATCH}&select=id,doi,title,publication_year,authorships,primary_location,cited_by_count"
        )
        for x in data.get("results") or []:
            if not x.get("title"):
                continue
            doi = re.sub(r"^https://doi\.org/", "", x["doi"]) if x.get("doi") else None
            m = re.match(r"^10\.48550/arxiv\.(.+)$", doi or "", re.I)
            arx = m.group(1) if m else None
            d = {
                "type": "article",
                "title": x["title"],
                "authors": [
                    n
                    for n in (
                        flip((a.get("author") or {}).get("display_name", ""))
                        for a in x.get("authorships") or []
                    )
                    if n
                ],
                "year": x.get("publication_year"),
                "venue": ((x.get("primary_location") or {}).get("source") or {}).get(
                    "display_name"
                ),
                "doi": None if arx else doi,
                "arxiv": arx,
                "cited": x.get("cited_by_count"),
                "fields": {},
            }
            out[_short(x["id"])] = {k: v for k, v in d.items() if v is not None}
    return out


# --- drawing, after kirsche's original charts: x is the year, height says how often a paper is cited ---


def _group_of(p: Paper) -> str:
    folders = p.get("folders") or []
    if folders:
        return folders[0].split("/")[0]
    return (p.get("tags") or [""])[0]


def _short_name(p: Paper) -> str:
    authors = p.get("authors") or []
    last = authors[0].split(",")[0] if authors else p.get("title", "")[:18]
    return f"{last}{' et al.' if len(authors) > 2 else ''}{' ' + str(p['year']) if p.get('year') else ''}"


def layout(
    g: Graph, ids: list, width: int = 1000, band_height: int = 160
) -> tuple[list, list]:
    """Positions on a year axis, in one band per folder (or tag), higher the more cited.

    Returns (placed nodes as dicts, band names).
    """
    groups = sorted(
        {_group_of(g.nodes[i].paper) for i in ids}, key=lambda s: (s == "", s.lower())
    )
    if len(groups) > 8:
        biggest = sorted(
            groups,
            key=lambda s: -sum(1 for i in ids if _group_of(g.nodes[i].paper) == s),
        )[:7]
        groups = sorted(biggest, key=str.lower) + ["Other"]
    band_of = {name: k for k, name in enumerate(groups)}
    years = [g.nodes[i].year for i in ids if g.nodes[i].year]
    y0, y1 = (min(years), max(years)) if years else (2000, 2001)
    span = max(1, y1 - y0)

    def x_of(year: int) -> float:
        return 40 + (year - y0) / span * (width - 80)

    def degree(i: str) -> int:
        return len(g.nodes[i].cites) + len(g.nodes[i].cited_by)

    most = max([1.0] + [math.log1p(g.nodes[i].cited) for i in ids])
    per_band: list = [[] for _ in groups]
    placed = []
    for i in sorted(ids, key=lambda i: (-degree(i), i)):
        n = g.nodes[i]
        band = band_of.get(_group_of(n.paper), len(groups) - 1)
        r = 3 + min(9, 1.6 * math.log1p(n.cited))
        x = x_of(n.year or y0)
        top = band * band_height + r + 4
        bottom = (band + 1) * band_height - r - 4
        want = bottom - (math.log1p(n.cited) / most) * (bottom - top)

        def free(y: float) -> bool:
            return all(
                math.hypot(q["x"] - x, q["y"] - y) >= q["r"] + r + 2
                for q in per_band[band]
            )

        y = min(bottom, max(top, want))
        for k in range(1, 200):
            if free(y):
                break
            step = math.ceil(k / 2) * (r + 1) * (1 if k % 2 else -1)
            c = want + step
            if top <= c <= bottom and free(c):
                y = c
                break
        p = {
            "id": i,
            "x": round(x, 1),
            "y": round(min(bottom, max(top, y)), 1),
            "r": round(r, 1),
            "band": band,
        }
        placed.append(p)
        per_band[band].append(p)
    return placed, groups


def graph_json(g: Graph, ids: Optional[list] = None) -> dict:
    """Nodes and edges as plain data, for other tools (networkx, Gephi, D3 ...)."""
    keep = set(ids if ids is not None else g.nodes)
    nodes = []
    for i in keep:
        n = g.nodes[i]
        p = n.paper
        nodes.append(
            {
                "id": i,
                "key": p.get("key"),
                "title": p.get("title"),
                "authors": p.get("authors", []),
                "year": n.year or None,
                "cited": n.cited,
                "doi": p.get("doi"),
                "arxiv": p.get("arxiv"),
                "folders": p.get("folders", []),
                "tags": p.get("tags", []),
            }
        )
    nodes.sort(key=lambda n: (n["year"] or 0, n["key"] or ""))
    edges = [{"source": a, "target": b} for a, b in g.edges if a in keep and b in keep]
    return {"format": "kirsche-graph", "version": 1, "nodes": nodes, "edges": edges}


def graph_html(g: Graph, ids: list, title: str = "Citation map") -> str:
    """A self-contained HTML page (no outside scripts) drawing the map: tap a paper to see its links."""
    import html as _html

    placed, groups = layout(g, ids)
    band_h = 160
    width = 1000
    height = max(1, len(groups)) * band_h + 30
    at = {p["id"]: p for p in placed}
    years = [g.nodes[i].year for i in ids if g.nodes[i].year]
    y0, y1 = (min(years), max(years)) if years else (2000, 2001)
    colors = [
        "#4e79a7",
        "#e8853a",
        "#59a14f",
        "#d9534f",
        "#5fa8a3",
        "#c9a227",
        "#a8729a",
        "#8d6e5a",
    ]
    esc = _html.escape
    parts = []
    for k, name in enumerate(groups):
        parts.append(
            f'<text class="band" x="6" y="{k * band_h + 16}">{esc(name or "No folder")}</text>'
        )
        if k:
            parts.append(
                f'<line class="sep" x1="0" x2="{width}" y1="{k * band_h}" y2="{k * band_h}"/>'
            )
    step = max(1, round((y1 - y0) / 10))
    for yr in range(y0, y1 + 1, step):
        x = 40 + (yr - y0) / max(1, y1 - y0) * (width - 80)
        parts.append(f'<text class="year" x="{x:.1f}" y="{height - 8}">{yr}</text>')
    for a, b in g.edges:
        if a in at and b in at:
            pa, pb = at[a], at[b]
            parts.append(
                f'<line class="edge" data-a="{a}" data-b="{b}" x1="{pa["x"]}" y1="{pa["y"]}" x2="{pb["x"]}" y2="{pb["y"]}"/>'
            )
    for p in placed:
        n = g.nodes[p["id"]]
        paper = n.paper
        tip = f"{paper.get('title', '')}\n{_short_name(paper)} · cited {n.cited}"
        color = colors[p["band"] % len(colors)]
        parts.append(
            f'<circle class="node" data-id="{p["id"]}" data-key="{esc(paper.get("key", ""))}" cx="{p["x"]}" cy="{p["y"]}" r="{p["r"]}" fill="{color}">'
            f"<title>{esc(tip)}</title></circle>"
        )
    info = {
        i: {
            "key": g.nodes[i].paper.get("key"),
            "title": g.nodes[i].paper.get("title"),
            "who": _short_name(g.nodes[i].paper),
            "cites": [c for c in g.nodes[i].cites if c in at],
            "by": [c for c in g.nodes[i].cited_by if c in at],
        }
        for i in at
    }
    data = json.dumps(info, ensure_ascii=False).replace("</", "<\\/")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<style>
:root {{ --bg:#fbfaf7; --fg:#22211f; --muted:#77736c; --line:#cfcac0; --edge:#9a958c; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#181816; --fg:#ebe8e1; --muted:#9a958c; --line:#3a3935; --edge:#6d6962; }} }}
body {{ margin:0; background:var(--bg); color:var(--fg); font:15px/1.45 system-ui, sans-serif; }}
header {{ padding:16px; }} h1 {{ font:600 20px Georgia, serif; margin:0 0 4px; }} p {{ margin:0; color:var(--muted); }}
.wrap {{ overflow:auto; padding:0 16px; }} svg {{ min-width:700px; width:100%; height:auto; }}
.band {{ fill:var(--muted); font-size:12px; }} .year {{ fill:var(--muted); font-size:11px; text-anchor:middle; }}
.sep {{ stroke:var(--line); stroke-dasharray:3 4; }} .edge {{ stroke:var(--edge); stroke-opacity:.45; }}
.node {{ stroke:var(--bg); stroke-width:1.5; cursor:pointer; }} .dim {{ opacity:.12; }} .edge.on {{ stroke:var(--fg); stroke-opacity:.9; }}
#info {{ padding:12px 16px 24px; min-height:3em; }} #info b {{ font-family:Georgia, serif; }} #info code {{ color:var(--muted); }}
</style></head><body>
<header><h1>{esc(title)}</h1><p>{len(at)} papers, {sum(1 for a, b in g.edges if a in at and b in at)} links. Across: year. Up: how often cited. Tap a paper.</p></header>
<div class="wrap"><svg viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">{''.join(parts)}</svg></div>
<div id="info"></div>
<script>
const info = {data};
const svg = document.querySelector("svg"), box = document.getElementById("info");
const name = (id) => info[id] ? info[id].who : id;
svg.addEventListener("click", (e) => {{
  const id = e.target.dataset && e.target.dataset.id;
  svg.querySelectorAll(".dim,.on").forEach((el) => el.classList.remove("dim", "on"));
  if (!id) {{ box.textContent = ""; return; }}
  const n = info[id], near = new Set([id, ...n.cites, ...n.by]);
  svg.querySelectorAll(".node").forEach((el) => {{ if (!near.has(el.dataset.id)) el.classList.add("dim"); }});
  svg.querySelectorAll(".edge").forEach((el) => {{ if (el.dataset.a === id || el.dataset.b === id) el.classList.add("on"); else el.classList.add("dim"); }});
  box.innerHTML = "";
  const t = document.createElement("div"); t.innerHTML = "<b></b> <code></code>";
  t.querySelector("b").textContent = n.title; t.querySelector("code").textContent = n.key; box.append(t);
  const line = (label, ids) => {{ const d = document.createElement("div"); d.textContent = label + ": " + (ids.map(name).join(", ") || "none"); box.append(d); }};
  line("Cites", n.cites); line("Cited by", n.by);
}});
</script></body></html>
"""
