"""
JobFS — WebDAV abstraction layer for OpenWorks workers.

Maps Python file operations to WebDAV calls over job-scoped shares.
Lazy: nothing is downloaded until actually read.
Scope-bound: the share token enforces access limits, not application logic.
"""

import io
import xml.etree.ElementTree as ET
from datetime import datetime
from dataclasses import dataclass
from typing import BinaryIO
from urllib.parse import urljoin, quote, unquote

import requests


@dataclass
class FileInfo:
    name: str
    path: str
    size: int
    modified: datetime | None
    is_dir: bool


class JobFS:
    """WebDAV filesystem scoped to a job share."""

    def __init__(self, webdav_url: str, token: str, deadline: datetime | None = None,
                 verify_tls: bool | str = True):
        self.base_url = webdav_url.rstrip("/")
        self.token = token
        self.deadline = deadline
        self._session = requests.Session()
        # Public shares use password as basic auth (user=public, pass=token)
        # Regular shares use Bearer token
        if "/public-files/" in webdav_url:
            self._session.auth = ("public", token)
        else:
            self._session.headers["Authorization"] = f"Bearer {token}"
        self._session.verify = verify_tls

    def _url(self, path: str) -> str:
        if path.startswith("/"):
            path = path[1:]
        return f"{self.base_url}/{quote(path, safe='/')}"

    def _check_deadline(self):
        if self.deadline and datetime.now(self.deadline.tzinfo) >= self.deadline:
            raise PermissionError("share deadline exceeded")

    # --- Read operations (lazy, on-demand) ---

    def ls(self, path: str = "/", recursive: bool = False) -> list[FileInfo]:
        """List directory contents via PROPFIND."""
        self._check_deadline()
        depth = "infinity" if recursive else "1"
        # Ensure trailing slash for directory listing
        if not path.endswith("/"):
            path = path + "/"
        body = '<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:allprop/></d:propfind>'
        resp = self._session.request(
            "PROPFIND",
            self._url(path),
            headers={"Depth": depth, "Content-Type": "application/xml"},
            data=body,
        )
        resp.raise_for_status()
        return self._parse_propfind(resp.text, skip_self=True)

    def stat(self, path: str) -> FileInfo:
        """Get file/directory metadata via PROPFIND Depth:0."""
        self._check_deadline()
        body = '<?xml version="1.0"?><d:propfind xmlns:d="DAV:"><d:allprop/></d:propfind>'
        resp = self._session.request(
            "PROPFIND",
            self._url(path),
            headers={"Depth": "0", "Content-Type": "application/xml"},
            data=body,
        )
        resp.raise_for_status()
        entries = self._parse_propfind(resp.text, skip_self=False)
        if not entries:
            raise FileNotFoundError(path)
        return entries[0]

    def read(self, path: str) -> bytes:
        """Download file content via GET."""
        self._check_deadline()
        resp = self._session.get(self._url(path))
        resp.raise_for_status()
        return resp.content

    def open(self, path: str) -> BinaryIO:
        """Open file as streaming file-like object via GET."""
        self._check_deadline()
        resp = self._session.get(self._url(path), stream=True)
        resp.raise_for_status()
        return io.BytesIO(resp.content)

    def exists(self, path: str) -> bool:
        """Check if path exists via PROPFIND Depth:0."""
        try:
            self.stat(path)
            return True
        except (requests.HTTPError, FileNotFoundError):
            return False

    # --- Write operations ---

    def write(self, path: str, data: bytes | BinaryIO) -> None:
        """Upload file via PUT."""
        self._check_deadline()
        if isinstance(data, (bytes, bytearray)):
            resp = self._session.put(self._url(path), data=data)
        else:
            resp = self._session.put(self._url(path), data=data)
        resp.raise_for_status()

    def mkdir(self, path: str) -> None:
        """Create directory via MKCOL."""
        self._check_deadline()
        resp = self._session.request("MKCOL", self._url(path))
        if resp.status_code not in (201, 405):  # 405 = already exists
            resp.raise_for_status()

    def delete(self, path: str) -> None:
        """Delete file or directory via DELETE."""
        self._check_deadline()
        resp = self._session.delete(self._url(path))
        resp.raise_for_status()

    def copy(self, src: str, dst: str) -> None:
        """Server-side copy via COPY."""
        self._check_deadline()
        resp = self._session.request(
            "COPY",
            self._url(src),
            headers={"Destination": self._url(dst)},
        )
        resp.raise_for_status()

    def move(self, src: str, dst: str) -> None:
        """Server-side move via MOVE."""
        self._check_deadline()
        resp = self._session.request(
            "MOVE",
            self._url(src),
            headers={"Destination": self._url(dst)},
        )
        resp.raise_for_status()

    # --- Helpers ---

    @staticmethod
    def basename(path: str) -> str:
        return path.rstrip("/").rsplit("/", 1)[-1]

    def _parse_propfind(self, xml_text: str, skip_self: bool) -> list[FileInfo]:
        ns = {"d": "DAV:"}
        root = ET.fromstring(xml_text)
        entries = []
        first = True

        for response in root.findall("d:response", ns):
            if skip_self and first:
                first = False
                continue
            first = False

            href = response.findtext("d:href", "", ns)
            name = unquote(href.rstrip("/").rsplit("/", 1)[-1])

            propstat = response.find("d:propstat", ns)
            if propstat is None:
                continue
            prop = propstat.find("d:prop", ns)
            if prop is None:
                continue

            is_dir = prop.find("d:resourcetype/d:collection", ns) is not None

            size_text = prop.findtext("d:getcontentlength", "0", ns)
            try:
                size = int(size_text)
            except ValueError:
                size = 0

            modified = None
            mod_text = prop.findtext("d:getlastmodified", None, ns)
            if mod_text:
                try:
                    modified = datetime.strptime(mod_text, "%a, %d %b %Y %H:%M:%S %Z")
                except ValueError:
                    pass

            entries.append(FileInfo(
                name=name,
                path=href,
                size=size,
                modified=modified,
                is_dir=is_dir,
            ))

        return entries
