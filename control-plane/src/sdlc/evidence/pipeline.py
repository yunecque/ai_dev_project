"""End-to-end tool-output capture: classify, compress, store, record."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..trust import TrustTier
from .compression import DEFAULT_MAX_BYTES, CompressionResult, compress_for_context
from .record import build_evidence_record
from .store import EvidenceStore


class SensitiveContentError(ValueError):
    """Raised when sensitive content would enter the model context."""


@dataclass(frozen=True)
class ToolOutputResult:
    """The evidence record plus the bounded text that may enter model context."""

    record: dict[str, Any]
    context_text: str
    digest: str


def process_tool_output(
    text: str,
    *,
    action: str,
    actor: Mapping[str, Any],
    run_id: str,
    artifact_id: str,
    created_at: str,
    store: EvidenceStore,
    tier: TrustTier = TrustTier.UNTRUSTED,
    sensitivity: str = "none",
    max_bytes: int = DEFAULT_MAX_BYTES,
    artifact_ref: str | None = None,
) -> ToolOutputResult:
    """Store the byte-exact original and return a bounded, schema-valid evidence record."""
    if tier is TrustTier.SENSITIVE:
        raise SensitiveContentError(
            "sensitive content must be redacted or handled outside the model context"
        )
    compression: CompressionResult = compress_for_context(text, tier=tier, max_bytes=max_bytes)
    digest = store.put(text.encode("utf-8"))
    if digest != compression.original_digest:
        raise AssertionError("evidence store digest mismatch")
    record = build_evidence_record(
        artifact_id=artifact_id,
        created_at=created_at,
        actor=actor,
        run_id=run_id,
        action=action,
        trust_tier=tier,
        sensitivity=sensitivity,
        artifact_digest=digest,
        artifact_ref=artifact_ref if artifact_ref is not None else compression.recovery_handle,
        compression=compression,
    )
    return ToolOutputResult(record=record, context_text=compression.context_text, digest=digest)