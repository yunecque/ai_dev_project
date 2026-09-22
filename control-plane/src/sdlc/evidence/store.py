"""Content-addressed evidence store for byte-exact originals."""

from __future__ import annotations

import hashlib
from pathlib import Path


class EvidenceStore:
    """Store raw bytes keyed by their SHA-256 digest."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def _path(self, digest: str) -> Path:
        return self._root / digest

    def put(self, data: bytes) -> str:
        digest = hashlib.sha256(data).hexdigest()
        self._root.mkdir(parents=True, exist_ok=True)
        self._path(digest).write_bytes(data)
        return digest

    def get(self, digest: str) -> bytes:
        path = self._path(digest)
        if not path.is_file():
            raise KeyError(digest)
        return path.read_bytes()

    def resolve(self, handle: str) -> bytes:
        prefix = "sha256:"
        if not handle.startswith(prefix):
            raise ValueError(f"unsupported recovery handle: {handle!r}")
        return self.get(handle[len(prefix) :])