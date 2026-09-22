"""Build ``evidence-record`` workflow artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ..trust import TrustTier
from .compression import CompressionResult


def build_evidence_record(
    *,
    artifact_id: str,
    created_at: str,
    actor: Mapping[str, Any],
    run_id: str,
    action: str,
    trust_tier: TrustTier,
    sensitivity: str,
    artifact_digest: str | None = None,
    artifact_ref: str | None = None,
    policy_decision_ref: str | None = None,
    compression: CompressionResult | None = None,
    links: Sequence[Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """Return a document validating against contracts/schemas/evidence-record.schema.json."""
    document: dict[str, Any] = {
        "schema_version": "1.0.0",
        "artifact_type": "evidence-record",
        "id": artifact_id,
        "created_at": created_at,
        "actor": dict(actor),
        "run_id": run_id,
        "action": action,
        "trust_tier": trust_tier.value,
        "sensitivity": sensitivity,
    }
    if artifact_digest is not None:
        document["artifact_digest"] = artifact_digest
    if artifact_ref is not None:
        document["artifact_ref"] = artifact_ref
    if policy_decision_ref is not None:
        document["policy_decision_ref"] = policy_decision_ref
    if compression is not None:
        entry: dict[str, Any] = {"applied": compression.applied}
        if compression.applied:
            entry["original_digest"] = compression.original_digest
            entry["original_size_bytes"] = compression.original_size_bytes
            entry["compressed_size_bytes"] = compression.compressed_size_bytes
            entry["recovery_handle"] = compression.recovery_handle
        document["compression"] = entry
    if links:
        document["links"] = [dict(link) for link in links]
    return document