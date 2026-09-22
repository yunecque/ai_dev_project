"""Compression layer for large untrusted tool output (ADR-0007).

Only large ``untrusted`` output is compressed: the model receives a bounded excerpt while the
byte-exact original is addressed in the evidence store by its SHA-256 digest. Canonical JSON
artifacts are never compressed.
"""

from __future__ import annotations

import hashlib
import zlib
from dataclasses import dataclass

from ..trust import TrustTier

DEFAULT_MAX_BYTES = 8192
DEFAULT_EXCERPT_BYTES = 2048


@dataclass(frozen=True)
class CompressionResult:
    """Outcome of preparing tool output for the model context."""

    applied: bool
    original_digest: str
    original_size_bytes: int
    compressed_size_bytes: int
    recovery_handle: str
    context_text: str


def _excerpt(raw: bytes, excerpt_bytes: int) -> str:
    head = raw[:excerpt_bytes]
    tail = raw[-excerpt_bytes:]
    omitted = len(raw) - len(head) - len(tail)
    marker = f"\n... [{omitted} bytes omitted; byte-exact original in evidence store] ...\n"
    return (head + marker.encode("utf-8") + tail).decode("utf-8", errors="replace")


def compress_for_context(
    text: str,
    *,
    tier: TrustTier,
    max_bytes: int = DEFAULT_MAX_BYTES,
    excerpt_bytes: int = DEFAULT_EXCERPT_BYTES,
) -> CompressionResult:
    """Return the context representation and recovery handle for ``text``."""
    raw = text.encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    handle = f"sha256:{digest}"
    if tier is not TrustTier.UNTRUSTED or len(raw) <= max_bytes:
        return CompressionResult(False, digest, len(raw), len(raw), handle, text)
    compressed = zlib.compress(raw, level=9)
    return CompressionResult(
        True,
        digest,
        len(raw),
        len(compressed),
        handle,
        _excerpt(raw, excerpt_bytes),
    )