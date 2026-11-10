"""Which libraries the CLI knows, and how to reach them.

Settings use the web app's own names (``storage.provider``,
``storage.s3.bucket``, ``storage.github.token`` ...), so a settings backup
exported from Lightkone (Settings → Backup → Export settings) can be read as it is.
They are kept in ``~/.config/kirsche/config.json`` (or ``$KIRSCHE_CONFIG``),
readable by you only. Keys and tokens never go into the library itself.
"""

from __future__ import annotations

import base64
import json
import os
import stat
from pathlib import Path
from typing import Optional

from kirsche.lightkone.storage import (
    FolderStorage,
    GitHubStorage,
    S3Storage,
    Storage,
    StorageError,
)

#: Settings worth keeping from a Lightkone backup: where the library lives, and the OpenAlex key.
KEEP_PREFIXES = ("storage.", "related.openalexKey")
PROVIDERS = ("folder", "s3", "github")


def config_path() -> Path:
    if os.environ.get("KIRSCHE_CONFIG"):
        return Path(os.environ["KIRSCHE_CONFIG"]).expanduser()
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "kirsche" / "config.json"


def load_config() -> dict:
    p = config_path()
    if not p.exists():
        return {"default": None, "libraries": {}}
    c = json.loads(p.read_text("utf-8"))
    c.setdefault("libraries", {})
    c.setdefault("default", None)
    return c


def save_config(c: dict) -> Path:
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(c, f, indent=2)
        f.write("\n")
    os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)
    return p


def keep(settings: dict) -> dict:
    return {
        k: v
        for k, v in settings.items()
        if isinstance(v, str) and k.startswith(KEEP_PREFIXES) and v != ""
    }


def read_backup(text: str, passphrase: str = "") -> dict:
    """The settings in a Lightkone settings backup (format ``lightkone-settings``), decrypting it if needed."""
    try:
        b = json.loads(text)
    except ValueError:
        raise ValueError("This is not a Lightkone settings file.")
    if not isinstance(b, dict) or b.get("format") != "lightkone-settings":
        raise ValueError("This is not a Lightkone settings file.")
    s = b.get("settings")
    if b.get("encrypted"):
        if not passphrase:
            raise ValueError("This backup is encrypted: give its passphrase.")
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        except ImportError:  # pragma: no cover
            raise ValueError(
                "Reading an encrypted backup needs the cryptography package: pip install 'kirsche[crypto]'."
            )
        e = b["encrypted"]
        try:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=base64.b64decode(e["salt"]),
                iterations=int(e["iterations"]),
            )
            key = kdf.derive(passphrase.encode("utf-8"))
            s = json.loads(
                AESGCM(key).decrypt(
                    base64.b64decode(e["iv"]), base64.b64decode(e["data"]), None
                )
            )
        except Exception:
            raise ValueError("Wrong passphrase, or the file is damaged.")
    if not isinstance(s, dict):
        raise ValueError("The backup holds no settings.")
    return {k: v for k, v in s.items() if isinstance(v, str)}


def storage_from(settings: dict) -> Storage:
    """The storage a library's settings point to."""
    provider = settings.get("storage.provider") or "browser"

    def get(name: str) -> str:
        return settings.get(f"storage.{provider}.{name}", "")

    if provider == "folder":
        if not get("path"):
            raise StorageError("This library's settings have no folder path.")
        return FolderStorage(get("path"))
    if provider == "s3":
        return S3Storage(
            endpoint=get("endpoint"),
            bucket=get("bucket"),
            access_key_id=get("accessKeyId"),
            secret_access_key=get("secretAccessKey"),
            region=get("region") or "auto",
            prefix=get("prefix"),
        )
    if provider == "github":
        return GitHubStorage(
            repo=get("repo"), token=get("token"), branch=get("branch"), api=get("api")
        )
    if provider == "browser":
        raise StorageError(
            "This library lives in a browser only, which the command line cannot reach. "
            "Move it to an S3/R2 bucket or a GitHub repository in Lightkone's Settings first."
        )
    raise StorageError(f"Unknown storage {provider!r}.")


def pick(name: Optional[str], directory: Optional[str] = None) -> tuple[str, dict]:
    """The settings of the library to use: a folder given on the command line, a named one, or the default."""
    if directory:
        if not Path(directory).expanduser().is_dir():
            raise StorageError(f"No folder {directory}.")
        return directory, {
            "storage.provider": "folder",
            "storage.folder.path": str(Path(directory).expanduser()),
        }
    env_dir = os.environ.get("LIGHTKONE_DIR")
    if not name and env_dir:
        return env_dir, {"storage.provider": "folder", "storage.folder.path": env_dir}
    c = load_config()
    name = name or os.environ.get("LIGHTKONE_LIBRARY") or c.get("default")
    if not name:
        raise StorageError(
            "No library set up yet. Run `kirsche login` first, or pass --dir PATH."
        )
    if name not in c["libraries"]:
        known = ", ".join(sorted(c["libraries"])) or "none"
        raise StorageError(f"No library called {name!r} (known: {known}).")
    return name, c["libraries"][name]
