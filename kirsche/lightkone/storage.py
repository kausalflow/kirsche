"""Where a library lives: the same three kinds of storage the Lightkone web app offers.

- ``FolderStorage``: a folder on disk, e.g. a clone of the library's GitHub
  repository, an rclone mount of the bucket, or a copy for offline work.
- ``S3Storage``: any S3-compatible bucket (Cloudflare R2, AWS S3, MinIO ...).
- ``GitHubStorage``: a (private) GitHub repository; every save is a commit.

Paths are relative to the storage's root, e.g. ``lightkone/library.json``.
"""

from __future__ import annotations

import base64
import datetime as _dt
import hashlib
import hmac
import os
import re
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests

USER_AGENT = "kirsche (Lightkone CLI; https://github.com/kausalflow/kirsche)"


def get_politely(
    http, url: str, headers: Optional[dict] = None, tries: int = 3, timeout: int = 60
):
    """GET, waiting and trying again when a free API says it is busy (429 or 503)."""
    import time

    headers = {"User-Agent": USER_AGENT, **(headers or {})}
    for attempt in range(tries):
        r = http.get(url, headers=headers, timeout=timeout)
        if r.status_code not in (429, 503) or attempt == tries - 1:
            return r
        wait = r.headers.get("Retry-After", "") if hasattr(r, "headers") else ""
        time.sleep(
            min(30, float(wait))
            if wait.replace(".", "", 1).isdigit()
            else 2 * (attempt + 1)
        )
    return r


class StorageError(RuntimeError):
    pass


class Storage:
    """A place a library lives."""

    def read(self, path: str) -> Optional[bytes]:
        """The file's bytes, or None when there is no such file."""
        raise NotImplementedError

    def write(
        self, path: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        raise NotImplementedError

    def list(self, prefix: str) -> list[str]:
        """Every file whose path starts with ``prefix``, in subfolders too."""
        raise NotImplementedError

    def remove(self, path: str) -> None:
        raise NotImplementedError

    def describe(self) -> str:
        return type(self).__name__


class FolderStorage(Storage):
    def __init__(self, root: str | os.PathLike):
        self.root = Path(root).expanduser()

    def _path(self, path: str) -> Path:
        p = (self.root / path).resolve()
        if self.root.resolve() not in p.parents and p != self.root.resolve():
            raise StorageError(f"{path} is outside the library folder.")
        return p

    def read(self, path):
        p = self._path(path)
        return p.read_bytes() if p.is_file() else None

    def write(self, path, data, content_type="application/octet-stream"):
        p = self._path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".kirsche-tmp")
        tmp.write_bytes(data)
        tmp.replace(p)

    def list(self, prefix):
        base = self.root.resolve()
        if not base.exists():
            return []
        out = []
        for f in base.rglob("*"):
            if f.is_file():
                rel = f.relative_to(base).as_posix()
                if rel.startswith(prefix) and not rel.startswith(".git/"):
                    out.append(rel)
        return sorted(out)

    def remove(self, path):
        p = self._path(path)
        if p.is_file():
            p.unlink()

    def describe(self):
        return f"folder {self.root}"


def _canonical_query(query: dict) -> str:
    return "&".join(
        f"{quote(k, safe='-_.~')}={quote(str(v), safe='-_.~')}"
        for k, v in sorted(query.items())
    )


def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


class S3Storage(Storage):
    """An S3-compatible bucket, with requests signed by AWS Signature Version 4."""

    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key_id: str,
        secret_access_key: str,
        region: str = "auto",
        prefix: str = "",
        session: Optional[requests.Session] = None,
    ):
        if not (endpoint and bucket and access_key_id and secret_access_key):
            raise StorageError(
                "S3 storage needs an endpoint, a bucket, an access key id and a secret."
            )
        self.endpoint = endpoint.rstrip("/")
        self.bucket = bucket
        self.key_id = access_key_id
        self.secret = secret_access_key
        self.region = region or "auto"
        self.prefix = prefix.strip("/")
        self.http = session or requests.Session()

    def _full(self, path: str) -> str:
        return f"{self.prefix}/{path}" if self.prefix else path

    def _url_path(self, key: str = "") -> str:
        base = "/" + quote(self.bucket, safe="")
        return base + (
            "/" + "/".join(quote(s, safe="") for s in key.split("/")) if key else ""
        )

    def signed_headers(
        self,
        method: str,
        path: str,
        query: dict,
        body: bytes,
        now: Optional[_dt.datetime] = None,
        extra: Optional[dict] = None,
    ) -> dict:
        now = now or _dt.datetime.now(_dt.timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        day = now.strftime("%Y%m%d")
        host = re.sub(r"^https?://", "", self.endpoint)
        payload = hashlib.sha256(body).hexdigest()
        headers = {
            "host": host,
            "x-amz-content-sha256": payload,
            "x-amz-date": amz_date,
        }
        for k, v in (extra or {}).items():
            headers[k.lower()] = v
        canonical_query = _canonical_query(query)
        names = sorted(headers)
        canonical_headers = "".join(f"{n}:{str(headers[n]).strip()}\n" for n in names)
        signed = ";".join(names)
        request = "\n".join(
            [method, path, canonical_query, canonical_headers, signed, payload]
        )
        scope = f"{day}/{self.region}/s3/aws4_request"
        to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                scope,
                hashlib.sha256(request.encode()).hexdigest(),
            ]
        )
        k = _sign(
            _sign(
                _sign(_sign(("AWS4" + self.secret).encode(), day), self.region), "s3"
            ),
            "aws4_request",
        )
        signature = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
        headers["authorization"] = (
            f"AWS4-HMAC-SHA256 Credential={self.key_id}/{scope}, SignedHeaders={signed}, Signature={signature}"
        )
        headers.pop("host")
        return headers

    def _request(
        self,
        method: str,
        key: str = "",
        query: Optional[dict] = None,
        body: bytes = b"",
        extra: Optional[dict] = None,
    ):
        query = query or {}
        path = self._url_path(key)
        headers = self.signed_headers(method, path, query, body, extra=extra)
        headers["user-agent"] = USER_AGENT
        qs = _canonical_query(query)
        url = self.endpoint + path + (f"?{qs}" if qs else "")
        return self.http.request(
            method, url, data=body or None, headers=headers, timeout=120
        )

    def read(self, path):
        r = self._request("GET", self._full(path))
        if r.status_code == 404:
            return None
        if not r.ok:
            raise StorageError(f"Storage read failed ({r.status_code}): {path}")
        return r.content

    def write(self, path, data, content_type="application/octet-stream"):
        r = self._request(
            "PUT", self._full(path), body=data, extra={"content-type": content_type}
        )
        if not r.ok:
            raise StorageError(f"Storage write failed ({r.status_code}): {path}")

    def list(self, prefix):
        keys: list[str] = []
        token = None
        while True:
            q = {"list-type": "2", "prefix": self._full(prefix)}
            if token:
                q["continuation-token"] = token
            r = self._request("GET", "", q)
            if not r.ok:
                raise StorageError(f"Storage list failed ({r.status_code})")
            xml = r.text
            for m in re.finditer(r"<Contents>[\s\S]*?<Key>([\s\S]*?)</Key>", xml):
                k = _unescape_xml(m.group(1))
                keys.append(k[len(self.prefix) + 1 :] if self.prefix else k)
            nxt = re.search(
                r"<NextContinuationToken>([\s\S]*?)</NextContinuationToken>", xml
            )
            if re.search(r"<IsTruncated>\s*true\s*</IsTruncated>", xml) and nxt:
                token = _unescape_xml(nxt.group(1))
            else:
                return keys

    def remove(self, path):
        r = self._request("DELETE", self._full(path))
        if not r.ok and r.status_code != 404:
            raise StorageError(f"Storage delete failed ({r.status_code}): {path}")

    def describe(self):
        return (
            f"bucket {self.bucket}"
            + (f"/{self.prefix}" if self.prefix else "")
            + f" at {self.endpoint}"
        )


def _unescape_xml(s: str) -> str:
    def one(m: re.Match) -> str:
        e = m.group(1)
        if e.startswith("#x") or e.startswith("#X"):
            return chr(int(e[2:], 16))
        if e.startswith("#"):
            return chr(int(e[1:]))
        return {"lt": "<", "gt": ">", "quot": '"', "apos": "'", "amp": "&"}[e.lower()]

    return re.sub(r"&(lt|gt|quot|apos|amp|#\d+|#x[0-9a-f]+);", one, s, flags=re.I)


class GitHubStorage(Storage):
    """A GitHub repository, through the contents API. Every write is a commit."""

    def __init__(
        self,
        repo: str,
        token: str,
        branch: str = "",
        api: str = "",
        session: Optional[requests.Session] = None,
    ):
        if not re.match(r"^[\w.-]+/[\w.-]+$", repo or "") or not token:
            raise StorageError(
                "GitHub storage needs a repository as owner/name and a token."
            )
        self.repo = repo
        self.token = token
        self.branch = branch
        self.api = (api or "https://api.github.com").rstrip("/")
        self.http = session or requests.Session()

    def _headers(self, accept: str = "application/vnd.github+json") -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": USER_AGENT,
        }

    def _contents(self, path: str) -> str:
        return f"{self.api}/repos/{self.repo}/contents/" + "/".join(
            quote(s, safe="") for s in path.split("/")
        )

    def _ref(self) -> dict:
        return {"ref": self.branch} if self.branch else {}

    def _sha(self, path: str) -> Optional[str]:
        r = self.http.get(
            self._contents(path),
            params=self._ref(),
            headers=self._headers("application/vnd.github.object+json"),
            timeout=60,
        )
        if r.status_code == 404:
            return None
        if not r.ok:
            raise StorageError(f"GitHub {r.status_code} reading {path}")
        return r.json().get("sha")

    def read(self, path):
        r = self.http.get(
            self._contents(path),
            params=self._ref(),
            headers=self._headers("application/vnd.github.raw+json"),
            timeout=120,
        )
        if r.status_code == 404:
            return None
        if not r.ok:
            raise StorageError(f"GitHub {r.status_code} reading {path}")
        return r.content

    def write(self, path, data, content_type="application/octet-stream"):
        body = {
            "message": f"Lightkone CLI: update {path}",
            "content": base64.b64encode(data).decode("ascii"),
        }
        sha = self._sha(path)
        if sha:
            body["sha"] = sha
        if self.branch:
            body["branch"] = self.branch
        r = self.http.put(
            self._contents(path), json=body, headers=self._headers(), timeout=120
        )
        if not r.ok:
            msg = ""
            try:
                msg = r.json().get("message", "")
            except ValueError:
                pass
            raise StorageError(f"GitHub {r.status_code} writing {path}: {msg}")

    def list(self, prefix):
        ref = quote(self.branch or "HEAD", safe="")
        r = self.http.get(
            f"{self.api}/repos/{self.repo}/git/trees/{ref}",
            params={"recursive": "1"},
            headers=self._headers(),
            timeout=120,
        )
        if r.status_code in (404, 409):
            return []
        if not r.ok:
            raise StorageError(f"GitHub {r.status_code} listing {self.repo}")
        return [
            i["path"]
            for i in r.json().get("tree", [])
            if i.get("type") == "blob" and i["path"].startswith(prefix)
        ]

    def remove(self, path):
        sha = self._sha(path)
        if not sha:
            return
        body = {"message": f"Lightkone CLI: remove {path}", "sha": sha}
        if self.branch:
            body["branch"] = self.branch
        r = self.http.delete(
            self._contents(path), json=body, headers=self._headers(), timeout=60
        )
        if not r.ok:
            raise StorageError(f"GitHub {r.status_code} removing {path}")

    def describe(self):
        return f"GitHub repository {self.repo}" + (
            f" ({self.branch})" if self.branch else ""
        )
