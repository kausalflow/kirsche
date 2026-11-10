"""The Lightkone command line, built with Typer. Installed as both ``kirsche`` and ``lightkone``.

It works on the same library the Lightkone web app uses: the files in your
S3/R2 bucket, GitHub repository or a folder on disk. Changes are merged with
what the app (or Claude through MCP) saved in the meantime, never overwritten.
"""

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import sys
from enum import Enum
from pathlib import Path
from typing import Annotated, List, NoReturn, Optional

import click
import typer

from kirsche.lightkone import settings as cfg
from kirsche.lightkone.bibtex import (
    library_to_bibtex,
    paper_to_bibtex,
    parse_bibtex_to_drafts,
)
from kirsche.lightkone.library import Library, clean_folder, now_iso
from kirsche.lightkone.storage import StorageError
from kirsche.version import __version__

LIBRARY = "Library"
PAPERS = "Papers"
FILES = "Files"
MAP = "Citation map"
WEB = "In the browser"
LEGACY_PANEL = "Standalone (from DOIs or a .bib file, no library)"

app = typer.Typer(
    name="kirsche",
    help=(
        "Lightkone from the command line: your papers, tags, folders, notes, BibTeX and citation map.\n\n"
        "Works on the same files as the Lightkone web app, wherever they live. "
        "Start with `login`, then try `ls`, `add 2106.09685` or `map`."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    add_completion=True,
    pretty_exceptions_show_locals=False,
)


class Sort(str, Enum):
    added = "added"
    year = "year"
    title = "title"  # type: ignore[assignment]
    relevance = "relevance"
    opened = "opened"


class Fmt(str, Enum):
    table = "table"
    keys = "keys"
    json = "json"
    bib = "bib"
    csv = "csv"


class ShowFmt(str, Enum):
    text = "text"
    json = "json"
    bib = "bib"


class ExportFmt(str, Enum):
    bib = "bib"
    json = "json"
    csv = "csv"
    keys = "keys"


class NoteFmt(str, Enum):
    text = "text"
    markdown = "markdown"
    json = "json"


class Provider(str, Enum):
    folder = "folder"
    s3 = "s3"
    github = "github"


# ---------------------------------------------------------------- state


class State:
    def __init__(self, library: Optional[str], directory: Optional[str]):
        self.name_opt = library
        self.dir_opt = directory
        self._lib: Optional[Library] = None
        self.settings: dict = {}
        self.name = ""

    def lib(self) -> Library:
        if self._lib is None:
            try:
                self.name, self.settings = cfg.pick(self.name_opt, self.dir_opt)
                self._lib = Library(cfg.storage_from(self.settings)).load()
            except (StorageError, ValueError) as e:
                fail(str(e))
        return self._lib  # type: ignore[return-value]

    def save(self) -> None:
        try:
            merged = self.lib().save()
        except StorageError as e:
            fail(str(e))
        if merged:
            typer.echo(
                f"Saved, with {merged} change{'s' if merged > 1 else ''} made elsewhere merged in.",
                err=True,
            )


def fail(message: str) -> NoReturn:
    """Stop with a plain, one-line error (no traceback)."""
    typer.secho(f"Error: {message}", fg="red", err=True)
    raise typer.Exit(1)


def _version(value: bool) -> None:
    if value:
        typer.echo(f"kirsche {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    library: Annotated[
        Optional[str],
        typer.Option(
            "--library",
            "-L",
            envvar="LIGHTKONE_LIBRARY",
            help="Which library to use (see `libraries`); the default otherwise.",
        ),
    ] = None,
    directory: Annotated[
        Optional[Path],
        typer.Option(
            "--dir",
            file_okay=False,
            help="Use the library in this folder (e.g. a clone of its GitHub repository).",
        ),
    ] = None,
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version", callback=_version, is_eager=True, help="Show the version."
        ),
    ] = None,
):
    ctx.obj = State(library, str(directory) if directory else None)


def state(ctx: typer.Context) -> State:
    return ctx.obj


# ---------------------------------------------------------------- output


def _width() -> int:
    return shutil.get_terminal_size((100, 20)).columns


def _first_author(p: dict) -> str:
    a = p.get("authors") or []
    if not a:
        return ""
    last = a[0].split(",")[0]
    return last + (
        " et al." if len(a) > 2 else f" & {a[1].split(',')[0]}" if len(a) == 2 else ""
    )


def _row(p: dict, width: int) -> str:
    star = "*" if p.get("starred") else " "
    head = f"{star}{p.get('key', ''):<22.22} {str(p.get('year') or ''):>4}  {_first_author(p):<20.20}  "
    return head + p.get("title", "")[: max(10, width - len(head))]


def _csv(papers: list) -> str:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(
        [
            "key",
            "title",
            "authors",
            "year",
            "venue",
            "doi",
            "arxiv",
            "tags",
            "folders",
            "starred",
            "added",
        ]
    )
    for p in papers:
        w.writerow(
            [
                p.get("key"),
                p.get("title"),
                "; ".join(p.get("authors", [])),
                p.get("year") or "",
                p.get("venue") or "",
                p.get("doi") or "",
                p.get("arxiv") or "",
                "; ".join(p.get("tags", [])),
                "; ".join(p.get("folders", [])),
                "yes" if p.get("starred") else "",
                p.get("added", ""),
            ]
        )
    return out.getvalue()


def _render(papers: list, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(papers, indent=1, ensure_ascii=False) + "\n"
    if fmt == "bib":
        return library_to_bibtex(papers)
    if fmt == "keys":
        return "".join(f"{p.get('key')}\n" for p in papers)
    if fmt == "csv":
        return _csv(papers)
    w = _width()
    return "".join(_row(p, w) + "\n" for p in papers)


def _emit(papers: list, fmt: str) -> None:
    typer.echo(_render(papers, fmt), nl=False)


def _papers(st: State, refs: Optional[List[str]], query: Optional[str]) -> list:
    """Papers named by citation key, DOI or arXiv id, or matching a search."""
    lib = st.lib()
    out = []
    for r in refs or []:
        p = lib.get(r)
        if p is None:
            fail(
                f"No paper {r!r} in the library (give a citation key, DOI or arXiv id)."
            )
        out.append(p)
    if query is not None:
        out += [p for p in lib.search(query) if p not in out]
    if not out:
        fail("Name papers by citation key, DOI or arXiv id, or pick them with --query.")
    return out


def _plural(n: int, word: str = "paper") -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


Refs = Annotated[
    Optional[List[str]],
    typer.Argument(help="Citation keys, DOIs or arXiv ids.", show_default=False),
]
QueryOpt = Annotated[
    Optional[str],
    typer.Option("--query", "-q", help="Also every paper matching this search."),
]
Words = Annotated[
    Optional[List[str]],
    typer.Argument(help="A search, in the app's syntax.", show_default=False),
]


# ---------------------------------------------------------------- library


@app.command(rich_help_panel=LIBRARY)
def login(
    name: Annotated[str, typer.Argument(help="A name for this library.")] = "main",
    backup: Annotated[
        Optional[Path],
        typer.Option(
            "--from-backup",
            exists=True,
            dir_okay=False,
            help="A settings backup exported from Lightkone (Settings → Backup → Export settings).",
        ),
    ] = None,
    passphrase: Annotated[
        Optional[str],
        typer.Option(
            help="The backup's passphrase, if it has one (asked for when needed)."
        ),
    ] = None,
    provider: Annotated[
        Optional[Provider],
        typer.Option(help="Set up by hand: where the library lives."),
    ] = None,
    pairs: Annotated[
        Optional[List[str]],
        typer.Option(
            "--set",
            metavar="FIELD=VALUE",
            help="Storage fields, e.g. bucket=papers (asked for when missing).",
        ),
    ] = None,
):
    """Tell the CLI where a library lives, and make it the default.

    Easiest: export your settings from Lightkone and read them in with
    `kirsche login --from-backup lightkone-settings.json`.
    Or by hand: `--provider s3` (endpoint, bucket, keys), `--provider github`
    (owner/name and a token), or `--provider folder --set path=~/papers`.
    """
    if backup:
        text = backup.read_text("utf-8")
        try:
            s = cfg.read_backup(text, passphrase or "")
        except ValueError as e:
            if "encrypted" in str(e) and not passphrase:
                try:
                    s = cfg.read_backup(
                        text, typer.prompt("Passphrase", hide_input=True)
                    )
                except ValueError as e2:
                    fail(str(e2))
            else:
                fail(str(e))
        s = cfg.keep(s)
    else:
        prov = (provider.value if provider else None) or typer.prompt(
            "Where does the library live (folder, s3, github)", default="s3"
        )
        if prov not in cfg.PROVIDERS:
            fail(f"Unknown storage {prov!r}: choose folder, s3 or github.")
        given = dict(p.split("=", 1) for p in pairs or [] if "=" in p)
        fields = {
            "folder": [("path", "Folder", False)],
            "s3": [
                (
                    "endpoint",
                    "Endpoint (https://<account>.r2.cloudflarestorage.com)",
                    False,
                ),
                ("bucket", "Bucket", False),
                ("region", "Region", False),
                ("prefix", "Folder in the bucket (blank for none)", False),
                ("accessKeyId", "Access key id", False),
                ("secretAccessKey", "Secret access key", True),
            ],
            "github": [
                ("repo", "Repository (owner/name)", False),
                ("token", "Token (fine-grained, Contents read and write)", True),
                ("branch", "Branch (blank for the default)", False),
            ],
        }[prov]
        s = {"storage.provider": prov}
        for field, label, secret in fields:
            if field in given:
                v = given[field]
            else:
                default = {"region": "auto"}.get(field, "")
                v = typer.prompt(
                    label,
                    default=default,
                    hide_input=secret,
                    show_default=bool(default),
                )
            if field == "path":
                v = str(Path(v).expanduser().resolve())
            if v:
                s[f"storage.{prov}.{field}"] = v
    try:
        lib = Library(cfg.storage_from(s)).load()
    except (StorageError, ValueError) as e:
        fail(f"Could not open the library: {e}")
    c = cfg.load_config()
    c["libraries"][name] = s
    c["default"] = name
    path = cfg.save_config(c)
    typer.echo(
        f"Library {name!r}: {lib.storage.describe()}, {_plural(len(lib.live))}. Saved to {path} (readable by you only)."
    )


@app.command(rich_help_panel=LIBRARY)
def libraries():
    """List the libraries the CLI knows (* marks the default)."""
    c = cfg.load_config()
    if not c["libraries"]:
        typer.echo("None yet. Run `kirsche login`.")
    for name, s in sorted(c["libraries"].items()):
        mark = "*" if name == c.get("default") else " "
        try:
            where = cfg.storage_from(s).describe()
        except StorageError as e:
            where = str(e)
        typer.echo(f"{mark} {name:<12} {where}")


@app.command(rich_help_panel=LIBRARY)
def use(name: Annotated[str, typer.Argument(help="A library from `libraries`.")]):
    """Make a library the default."""
    c = cfg.load_config()
    if name not in c["libraries"]:
        fail(f"No library called {name!r}.")
    c["default"] = name
    cfg.save_config(c)
    typer.echo(f"Using {name!r}.")


@app.command(rich_help_panel=LIBRARY)
def logout(name: Annotated[str, typer.Argument(help="A library from `libraries`.")]):
    """Forget a library's settings (the library itself is untouched)."""
    c = cfg.load_config()
    if c["libraries"].pop(name, None) is None:
        fail(f"No library called {name!r}.")
    if c.get("default") == name:
        c["default"] = next(iter(sorted(c["libraries"])), None)
    cfg.save_config(c)
    typer.echo(f"Forgot {name!r}.")


@app.command(rich_help_panel=LIBRARY)
def info(ctx: typer.Context):
    """Where the current library lives and what is in it."""
    st = state(ctx)
    lib = st.lib()
    live = lib.live
    typer.echo(f"Library:  {st.name} ({lib.storage.describe()})")
    typer.echo(
        f"Papers:   {len(live)} ({sum(1 for p in lib.papers if p.get('trashed'))} in the trash)"
    )
    typer.echo(f"Starred:  {sum(1 for p in live if p.get('starred'))}")
    typer.echo(
        f"With PDF: {sum(1 for p in live if p.get('pdf'))} in storage, {sum(1 for p in live if p.get('file') and not p.get('pdf'))} more with a Paperpile path"
    )
    typer.echo(
        f"Tags:     {len(lib.tag_counts())}   Folders: {len(lib.folder_counts())}"
    )


# ---------------------------------------------------------------- papers


@app.command(name="ls", rich_help_panel=PAPERS)
def ls(
    ctx: typer.Context,
    query: Words = None,
    sort: Annotated[Sort, typer.Option("--sort", "-s")] = Sort.added,
    limit: Annotated[
        int, typer.Option("--limit", "-n", help="Show at most this many (0: all).")
    ] = 0,
    fmt: Annotated[Fmt, typer.Option("--format", "-o")] = Fmt.table,
):
    """List or search papers, with the app's search syntax.

    Examples: `kirsche ls gravitational lensing`,
    `kirsche ls author:hinton year:2010-2015 tag:"deep learning"`,
    `kirsche ls in:Physics/QFT is:starred has:pdf -o bib > qft.bib`.
    Filters: tag: author: year: in: is:starred|recent|trash has:/no:pdf|abstract|arxiv|notes.
    """
    papers = state(ctx).lib().search(" ".join(query or []), sort.value)
    total = len(papers)
    if limit:
        papers = papers[:limit]
    _emit(papers, fmt.value)
    if fmt == Fmt.table and sys.stdout.isatty():
        typer.echo(
            _plural(total)
            + (f", showing {len(papers)}" if len(papers) < total else ""),
            err=True,
        )


@app.command(rich_help_panel=PAPERS)
def show(
    ctx: typer.Context,
    ref: Annotated[str, typer.Argument(help="Citation key, DOI or arXiv id.")],
    fmt: Annotated[ShowFmt, typer.Option("--format", "-o")] = ShowFmt.text,
):
    """One paper: its record, folders, tags, notes and abstract."""
    p = _papers(state(ctx), [ref], None)[0]
    if fmt == ShowFmt.json:
        typer.echo(json.dumps(p, indent=1, ensure_ascii=False))
        return
    if fmt == ShowFmt.bib:
        typer.echo(paper_to_bibtex(p), nl=False)
        return
    typer.secho(p.get("title", ""), bold=True)
    typer.echo("; ".join(p.get("authors", [])))
    typer.echo(
        " · ".join(
            b
            for b in [str(p["year"]) if p.get("year") else "", p.get("venue") or ""]
            if b
        )
    )
    typer.echo()
    rows = [
        ("Key", p.get("key")),
        ("DOI", p.get("doi")),
        ("arXiv", p.get("arxiv")),
        ("URL", p.get("url")),
        ("Folders", ", ".join(p.get("folders", []))),
        ("Tags", ", ".join(p.get("tags", []))),
        ("PDF", p.get("pdf") or (f"(Paperpile) {p['file']}" if p.get("file") else "")),
        ("Starred", "yes" if p.get("starred") else ""),
        ("Trashed", p.get("trashed")),
        ("Added", p.get("added")),
    ]
    for k, v in rows:
        if v:
            typer.echo(f"{k:<8} {v}")
    if p.get("notes"):
        typer.echo()
        typer.secho("Notes", bold=True)
        typer.echo(p["notes"])
    if p.get("abstract"):
        typer.echo()
        typer.secho("Abstract", bold=True)
        typer.echo(click.wrap_text(p["abstract"], min(_width(), 100)))


@app.command(rich_help_panel=PAPERS)
def add(
    ctx: typer.Context,
    refs: Annotated[
        List[str], typer.Argument(help="DOIs, arXiv ids, or links holding one.")
    ],
    tags: Annotated[
        Optional[List[str]], typer.Option("--tag", "-t", help="Tag the new papers.")
    ] = None,
    folders: Annotated[
        Optional[List[str]],
        typer.Option(
            "--folder", "-f", help="Put the new papers in a folder, e.g. Physics/QFT."
        ),
    ] = None,
):
    """Add papers by DOI, arXiv id, or a link holding one.

    Example: `kirsche add 10.1103/PhysRevLett.116.061102 2106.09685 -t lensing -f Physics/GR`.
    """
    from kirsche.lightkone.lookup import resolve

    st = state(ctx)
    lib = st.lib()
    drafts = []
    for r in refs:
        try:
            d = resolve(r)
        except Exception as e:  # network or service error
            fail(f"{r}: {e}")
        if d is None:
            fail(f"{r}: not a DOI or arXiv id, or no record found.")
        d["tags"] = list(dict.fromkeys([*d.get("tags", []), *(tags or [])]))
        if folders:
            d["folders"] = [clean_folder(f) for f in folders]
        drafts.append(d)
    added, updated = lib.merge(drafts)
    st.save()
    for p in added:
        typer.echo(f"Added   {p['key']}  {p['title']}")
    for p in updated:
        typer.echo(f"Updated {p['key']}  {p['title']} (already in the library)")
    done = {id(p) for p in added + updated}
    for d in drafts:
        if id(lib.find_duplicate(d)) not in done:
            typer.echo(f"Already there: {d['title']}")


@app.command(name="import", rich_help_panel=PAPERS)
def import_(
    ctx: typer.Context,
    files: Annotated[
        List[Path], typer.Argument(exists=True, dir_okay=False, help="BibTeX files.")
    ],
    tags: Annotated[
        Optional[List[str]],
        typer.Option("--tag", "-t", help="Tag every imported paper."),
    ] = None,
    folders: Annotated[
        Optional[List[str]],
        typer.Option("--folder", "-f", help="Put every imported paper in this folder."),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Only say what would happen.")
    ] = False,
):
    """Import papers from BibTeX files. Papers already there only gain missing fields, tags and folders."""
    st = state(ctx)
    lib = st.lib()
    drafts = []
    for f in files:
        for d in parse_bibtex_to_drafts(f.read_text("utf-8", errors="replace")):
            d["tags"] = list(dict.fromkeys([*d.get("tags", []), *(tags or [])]))
            if folders:
                d["folders"] = [clean_folder(x) for x in folders]
            drafts.append(d)
    added, updated = lib.merge(drafts)
    typer.echo(
        f"{len(drafts)} entries: {len(added)} new, {len(updated)} updated, {len(drafts) - len(added) - len(updated)} unchanged."
    )
    if dry_run:
        typer.echo("Dry run: nothing saved.")
    else:
        st.save()


def _edit_list(
    st: State,
    papers: list,
    field: str,
    add_: Optional[List[str]],
    remove: Optional[List[str]],
    clean=lambda s: s.strip(),
) -> None:
    plus = [clean(x) for x in add_ or [] if clean(x)]
    minus = [clean(x) for x in remove or []]
    if not plus and not minus:
        for p in papers:
            typer.echo(f"{p['key']}: {', '.join(p.get(field, [])) or '(none)'}")
        return
    changed = 0
    for p in papers:
        before = list(p.get(field, []))
        after = [x for x in dict.fromkeys([*before, *plus]) if x not in minus]
        if after != before:
            p[field] = after
            changed += 1
    st.save()
    typer.echo(f"Changed {changed} of {_plural(len(papers))}.")


@app.command(rich_help_panel=PAPERS)
def tag(
    ctx: typer.Context,
    refs: Refs = None,
    add_: Annotated[
        Optional[List[str]], typer.Option("--add", "-a", help="Tag to add.")
    ] = None,
    remove: Annotated[
        Optional[List[str]], typer.Option("--remove", "-r", help="Tag to take off.")
    ] = None,
    query: QueryOpt = None,
):
    """Add or remove tags (shows them when neither is given).

    Examples: `kirsche tag Hinton2012-in -a dropout -r todo`,
    `kirsche tag -q 'author:einstein year:1915' -a classics`.
    """
    st = state(ctx)
    _edit_list(st, _papers(st, refs, query), "tags", add_, remove)


@app.command(rich_help_panel=PAPERS)
def folder(
    ctx: typer.Context,
    refs: Refs = None,
    add_: Annotated[
        Optional[List[str]],
        typer.Option("--add", "-a", help="Folder to put them in, e.g. Physics/QFT."),
    ] = None,
    remove: Annotated[
        Optional[List[str]],
        typer.Option("--remove", "-r", help="Folder to take them out of."),
    ] = None,
    query: QueryOpt = None,
):
    """Put papers in folders or take them out (a paper can be in several)."""
    st = state(ctx)
    _edit_list(st, _papers(st, refs, query), "folders", add_, remove, clean_folder)


@app.command(rich_help_panel=PAPERS)
def note(
    ctx: typer.Context,
    ref: Annotated[str, typer.Argument(help="Citation key, DOI or arXiv id.")],
    text: Annotated[
        Optional[List[str]],
        typer.Argument(
            help="What to add; read from standard input when left out.",
            show_default=False,
        ),
    ] = None,
    replace: Annotated[
        bool,
        typer.Option("--replace", help="Replace the notes instead of adding to them."),
    ] = False,
):
    """Add to a paper's notes (Markdown)."""
    st = state(ctx)
    p = _papers(st, [ref], None)[0]
    body = (" ".join(text) if text else sys.stdin.read()).strip()
    if not body and not replace:
        fail("Nothing to add.")
    old = p.get("notes") or ""
    new = body if replace or not old else f"{old.rstrip()}\n\n{body}"
    st.lib().update(p, notes=new or None)
    st.save()
    typer.echo(f"Notes on {p['key']} saved.")


@app.command(rich_help_panel=PAPERS)
def star(
    ctx: typer.Context,
    refs: Refs = None,
    off: Annotated[bool, typer.Option("--off", help="Take the star off.")] = False,
    query: QueryOpt = None,
):
    """Star papers (or take stars off with --off)."""
    st = state(ctx)
    papers = _papers(st, refs, query)
    for p in papers:
        st.lib().update(p, starred=None if off else True)
    st.save()
    typer.echo(f"{'Unstarred' if off else 'Starred'} {_plural(len(papers))}.")


@app.command(rich_help_panel=PAPERS)
def trash(
    ctx: typer.Context,
    refs: Refs = None,
    restore: Annotated[
        bool, typer.Option("--restore", help="Take them out of the trash.")
    ] = False,
    query: Annotated[
        Optional[str],
        typer.Option(
            "--query",
            "-q",
            help="Also every paper matching this search (add is:trash to restore).",
        ),
    ] = None,
):
    """Move papers to the trash, or restore them. Nothing is deleted for good."""
    st = state(ctx)
    papers = _papers(st, refs, query)
    for p in papers:
        st.lib().update(p, trashed=None if restore else now_iso())
    st.save()
    typer.echo(f"{'Restored' if restore else 'Trashed'} {_plural(len(papers))}.")


@app.command(rich_help_panel=PAPERS)
def tags(ctx: typer.Context):
    """Every tag and how many papers carry it."""
    for t, n in state(ctx).lib().tag_counts():
        typer.echo(f"{n:>5}  {t}")


@app.command(rich_help_panel=PAPERS)
def folders(ctx: typer.Context):
    """Every folder and how many papers are in it (with the ones inside)."""
    for f, n in state(ctx).lib().folder_counts():
        typer.echo(f"{n:>5}  {'  ' * f.count('/')}{f.split('/')[-1]}")


# ---------------------------------------------------------------- files


@app.command(rich_help_panel=FILES)
def export(
    ctx: typer.Context,
    query: Words = None,
    fmt: Annotated[ExportFmt, typer.Option("--format", "-f")] = ExportFmt.bib,
    output: Annotated[
        Optional[Path],
        typer.Option(
            "--output",
            "-o",
            dir_okay=False,
            help="Write to this file instead of standard output.",
        ),
    ] = None,
):
    """Export the library, or the papers matching a search, as BibTeX, JSON or CSV.

    Examples: `kirsche export in:Thesis -o thesis.bib`, `kirsche export tag:lensing -f csv -o lensing.csv`.
    """
    papers = (
        state(ctx)
        .lib()
        .search(" ".join(query or []), "title" if fmt == ExportFmt.bib else "added")
    )
    text = _render(papers, fmt.value)
    if output:
        output.write_text(text, "utf-8")
        typer.echo(f"Wrote {_plural(len(papers))} to {output}.", err=True)
    else:
        typer.echo(text, nl=False)


@app.command(rich_help_panel=FILES)
def pdf(
    ctx: typer.Context,
    ref: Annotated[str, typer.Argument(help="Citation key, DOI or arXiv id.")],
    output: Annotated[
        Optional[Path],
        typer.Option(
            "--output",
            "-o",
            help="File or folder to save to (default: its file name, here).",
        ),
    ] = None,
    open_: Annotated[bool, typer.Option("--open", help="Open it afterwards.")] = False,
):
    """Download a paper's PDF from the library's storage."""
    st = state(ctx)
    lib = st.lib()
    p = _papers(st, [ref], None)[0]
    path = p.get("pdf") or (
        f"papers/{p['file'].split(';')[0].strip()}" if p.get("file") else None
    )
    data = lib.storage.read(path) if path else None
    if data is None:
        fail(
            f"{p['key']} has no PDF in this library's storage. Attach one with `attach`."
        )
    target = output or Path(Path(path).name)  # type: ignore[arg-type]
    if target.is_dir():
        target = target / Path(path).name  # type: ignore[arg-type]
    target.write_bytes(data)  # type: ignore[arg-type]
    typer.echo(str(target))
    if open_:
        typer.launch(str(target))


@app.command(rich_help_panel=FILES)
def attach(
    ctx: typer.Context,
    ref: Annotated[str, typer.Argument(help="Citation key, DOI or arXiv id.")],
    file: Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="The PDF.")],
):
    """Put a PDF into storage for a paper, filed like Paperpile (papers/All Papers/AUTHOR/...)."""
    st = state(ctx)
    lib = st.lib()
    p = _papers(st, [ref], None)[0]
    data = file.read_bytes()
    if not data.startswith(b"%PDF"):
        fail(f"{file} is not a PDF.")
    where, paperpile = lib.pdf_location(p)
    lib.storage.write(where, data, "application/pdf")
    lib.update(p, pdf=where, file=p.get("file") or paperpile)
    st.save()
    typer.echo(f"Stored as {where}")


@app.command(rich_help_panel=FILES)
def text(
    ctx: typer.Context,
    ref: Annotated[str, typer.Argument(help="Citation key, DOI or arXiv id.")],
):
    """Print a paper's full text, once Lightkone's reader has extracted it."""
    st = state(ctx)
    lib = st.lib()
    p = _papers(st, [ref], None)[0]
    data = lib.storage.read(f"lightkone/text/{p['id']}.txt")
    if data is None:
        fail(f"No text for {p['key']} yet: open it once in Lightkone's reader.")
    typer.echo(data.decode("utf-8", errors="replace"))  # type: ignore[union-attr]


@app.command(rich_help_panel=FILES)
def highlights(
    ctx: typer.Context,
    ref: Annotated[str, typer.Argument(help="Citation key, DOI or arXiv id.")],
    fmt: Annotated[NoteFmt, typer.Option("--format", "-o")] = NoteFmt.text,
):
    """A paper's highlights and their notes."""
    st = state(ctx)
    lib = st.lib()
    p = _papers(st, [ref], None)[0]
    raw = lib.storage.read(f"lightkone/annotations/{p['id']}.json")
    hs = []
    if raw:
        f = json.loads(raw.decode("utf-8"))
        if f.get("format") == "lightkone-annotations":
            hs = sorted(
                f.get("highlights", []),
                key=lambda h: (h.get("page", 0), (h.get("rects") or [[0, 0]])[0][1]),
            )
    if fmt == NoteFmt.json:
        typer.echo(json.dumps(hs, indent=1, ensure_ascii=False))
        return
    if not hs:
        typer.echo(f"No highlights on {p['key']}.", err=True)
        return
    if fmt == NoteFmt.markdown:
        typer.echo(f"# {p.get('title', '')}\n")
    for h in hs:
        if fmt == NoteFmt.markdown:
            typer.echo(f"> {h.get('text', '').strip()}\n>\n> p. {h.get('page')}\n")
            if h.get("note"):
                typer.echo(h["note"].strip() + "\n")
        else:
            typer.echo(f"p.{h.get('page')}  {h.get('text', '').strip()}")
            if h.get("note"):
                typer.echo(f"       note: {h['note'].strip()}")


# ---------------------------------------------------------------- the web app

DEFAULT_URL = "https://lightkone.lab.kausalflow.com/app/"
UrlOpt = Annotated[
    Optional[str],
    typer.Option(
        "--url",
        envvar="LIGHTKONE_URL",
        help=f"The Lightkone app's address (default {DEFAULT_URL}).",
    ),
]
PrintOpt = Annotated[bool, typer.Option("--print", help="Only print the address.")]


def app_url(url: Optional[str], paper: Optional[dict] = None, page: int = 0) -> str:
    """The app's address, opening a paper (and its reader at a page) when given, as Lightkone's own links do."""
    from urllib.parse import urlencode, urlsplit, urlunsplit

    parts = urlsplit(url or DEFAULT_URL)
    query = {}
    if paper is not None:
        query["open"] = paper["id"]
        if page:
            query["page"] = str(page)
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path or "/", urlencode(query), "")
    )


def _launch(address: str, print_only: bool) -> None:
    typer.echo(address)
    if not print_only:
        typer.launch(address)


@app.command(rich_help_panel=WEB)
def web(url: UrlOpt = None, print_only: PrintOpt = False):
    """Open the Lightkone web app in your browser, to read and explore.

    The browser uses the storage set up in its own Lightkone Settings (keys stay
    per browser), so set the same library up there once.
    """
    _launch(app_url(url), print_only)


@app.command(name="open", rich_help_panel=WEB)
def open_paper(
    ctx: typer.Context,
    ref: Annotated[str, typer.Argument(help="Citation key, DOI or arXiv id.")],
    page: Annotated[
        int,
        typer.Option(
            "--page",
            "-p",
            help="Open the reader at this page (needs the PDF in storage).",
        ),
    ] = 0,
    url: UrlOpt = None,
    print_only: PrintOpt = False,
):
    """Open a paper in the Lightkone web app: its details, or the reader at a page."""
    p = _papers(state(ctx), [ref], None)[0]
    _launch(app_url(url, p, page), print_only)


# ---------------------------------------------------------------- citation map


def _openalex(st: State, key: Optional[str]):
    from kirsche.lightkone.citations import OpenAlex

    return OpenAlex(
        key
        or os.environ.get("OPENALEX_API_KEY")
        or st.settings.get("related.openalexKey")
        or None
    )


def _graph(st: State, query: str, fetch: bool, key: Optional[str]):
    from kirsche.lightkone.citations import (
        build_graph,
        fetch_citations,
        load_citations,
        needs_fetch,
        save_citations,
    )

    lib = st.lib()
    store = load_citations(lib)
    todo = len(needs_fetch(lib.papers, store)) if fetch else 0
    if todo:
        oa = _openalex(st, key)
        with typer.progressbar(
            length=todo, label="References from OpenAlex", file=sys.stderr
        ) as bar:
            last = [0]

            def progress(done, total):
                bar.update(done - last[0])
                last[0] = done

            try:
                fetch_citations(lib.papers, store, oa, progress)
            except RuntimeError as e:
                fail(str(e))
            finally:
                save_citations(lib, store)
    g = build_graph(lib.papers, store)
    ids = [p["id"] for p in lib.search(query)] if query else list(g.nodes)
    return lib, store, g, [i for i in ids if i in g.nodes]


NoFetch = Annotated[
    bool, typer.Option("--no-fetch", help="Use only references already fetched.")
]
OAKey = Annotated[
    Optional[str],
    typer.Option(
        "--openalex-key",
        envvar="OPENALEX_API_KEY",
        help="An OpenAlex API key, for a daily budget of your own.",
    ),
]


@app.command(name="map", rich_help_panel=MAP)
def map_(
    ctx: typer.Context,
    query: Words = None,
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            dir_okay=False,
            help="An .html page to open in a browser; .json, .graphml or .gexf (Gephi, networkx), or .csv (plus -edges.csv) for other tools.",
        ),
    ] = Path("citation-map.html"),
    linked_only: Annotated[
        bool,
        typer.Option("--linked-only", help="Leave out papers with no link to another."),
    ] = False,
    no_fetch: NoFetch = False,
    openalex_key: OAKey = None,
    open_: Annotated[
        bool, typer.Option("--open", help="Open the page afterwards.")
    ] = False,
):
    """Draw which of your papers cite which (the app's Citation map), as a page or JSON.

    References come from OpenAlex and are kept in the library, shared with the
    web app, so each paper is looked up once. Examples: `kirsche map`,
    `kirsche map in:Thesis --open`, `kirsche map tag:lensing -o lensing.json`.
    """
    from kirsche.lightkone.citations import graph_html, graph_json

    st = state(ctx)
    q = " ".join(query or [])
    lib, store, g, ids = _graph(st, q, not no_fetch, openalex_key)
    if linked_only:
        ids = [i for i in ids if g.nodes[i].cites or g.nodes[i].cited_by]
    keep = set(ids)
    links = sum(1 for a, b in g.edges if a in keep and b in keep)
    suffix = output.suffix.lower()
    if suffix == ".json":
        output.write_text(
            json.dumps(graph_json(g, ids), indent=1, ensure_ascii=False) + "\n", "utf-8"
        )
    elif suffix in (".graphml", ".gexf"):
        try:
            import networkx as nx
        except ImportError:
            fail("GraphML and GEXF need networkx: pip install 'kirsche[graph]'.")
        nxg = g.subgraph(ids).to_networkx()
        (nx.write_graphml if suffix == ".graphml" else nx.write_gexf)(nxg, str(output))
    elif suffix == ".csv":
        nodes, edges = g.subgraph(ids).to_dataframes()
        for col in ("authors", "folders", "tags"):
            nodes[col] = nodes[col].map("; ".join)
        nodes.to_csv(output, index=False)
        edge_file = output.with_name(output.stem + "-edges.csv")
        edges.to_csv(edge_file, index=False)
        typer.echo(f"Links in {edge_file}.", err=True)
    else:
        output.write_text(
            graph_html(g, ids, f"Citation map: {q}" if q else "Citation map"), "utf-8"
        )
    known = sum(1 for i in ids if (store["works"].get(i) or {}).get("oa"))
    typer.echo(
        f"{_plural(len(ids))} ({known} found in OpenAlex), {_plural(links, 'link')}. Wrote {output}."
    )
    if open_:
        typer.launch(str(output))


@app.command(rich_help_panel=MAP)
def missing(
    ctx: typer.Context,
    query: Words = None,
    min_: Annotated[
        int, typer.Option("--min", help="Cited by at least this many of your papers.")
    ] = 2,
    limit: Annotated[int, typer.Option("--limit", "-n")] = 20,
    add_: Annotated[
        bool, typer.Option("--add", help="Add them all to the library.")
    ] = False,
    tags: Annotated[
        Optional[List[str]], typer.Option("--tag", "-t", help="Tag the ones added.")
    ] = None,
    no_fetch: NoFetch = False,
    openalex_key: OAKey = None,
    fmt: Annotated[Fmt, typer.Option("--format", "-o")] = Fmt.table,
):
    """Works your papers keep citing that the library doesn't have, most cited by you first."""
    from kirsche.lightkone.citations import build_graph, works_by_id

    st = state(ctx)
    q = " ".join(query or [])
    lib, store, _, ids = _graph(st, q, not no_fetch, openalex_key)
    keep = set(ids)
    g = build_graph([p for p in lib.papers if p["id"] in keep], store, min_)
    top = g.missing[:limit]
    if not top:
        typer.echo("Nothing cited that often is missing.", err=True)
        return
    try:
        records = works_by_id([oa for oa, _ in top], _openalex(st, openalex_key))
    except RuntimeError as e:
        fail(str(e))
    rows = []
    for oa, by in top:
        d = records.get(oa)
        if d:
            rows.append((d, by))
    if fmt == Fmt.table:
        w = _width()
        for d, by in rows:
            head = f"{len(by):>3}x  {str(d.get('year') or ''):>4}  {_first_author(d):<20.20}  "
            typer.echo(head + d["title"][: max(10, w - len(head))])
    else:
        _emit(
            [
                {
                    **{k: v for k, v in d.items() if k != "cited"},
                    "key": d.get("doi") or d.get("arxiv") or oa,
                    "tags": [],
                }
                for (d, _), (oa, _b) in zip(rows, top)
            ],
            fmt.value,
        )
    if add_:
        drafts = [
            {**{k: v for k, v in d.items() if k != "cited"}, "tags": list(tags or [])}
            for d, _ in rows
        ]
        added, _u = lib.merge(drafts)
        st.save()
        typer.echo(f"Added {_plural(len(added))}.", err=True)


# ---------------------------------------------------------------- the original standalone commands

LEGACY = {
    "metadata": "Download Semantic Scholar metadata for DOIs or a .bib file.",
    "connections": "Connect papers from DOIs, a .bib file or a metadata file.",
    "connections-from-metadata": "Connect papers in a downloaded metadata file.",
    "visualization": "Draw papers from DOIs or a .bib file as an HTML graph.",
}


def _legacy(name: str):
    def run(ctx: typer.Context):
        from kirsche import command as legacy

        cmd = legacy.kirsche.get_command(ctx, name) or legacy.kirsche.get_command(
            ctx, name.replace("-", "_")
        )
        cmd.main(
            args=ctx.args,
            prog_name=f"{ctx.find_root().info_name} {name}",
            standalone_mode=True,
        )

    run.__doc__ = LEGACY[name]
    return run


for _name in LEGACY:
    app.command(
        name=_name,
        rich_help_panel=LEGACY_PANEL,
        add_help_option=False,
        context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
    )(_legacy(_name))


def run() -> None:
    app()


if __name__ == "__main__":  # pragma: no cover
    run()
