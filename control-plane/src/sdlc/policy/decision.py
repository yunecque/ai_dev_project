"""Build a ``policy-decision`` workflow artifact from a PolicyResult."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .client import PolicyResult


def build_policy_decision(
    result: PolicyResult,
    *,
    artifact_id: str,
    created_at: str,
    actor: Mapping[str, Any],
    run_id: str,
    point: str,
    links: Sequence[Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """Return a document validating against contracts/schemas/policy-decision.schema.json."""
    document: dict[str, Any] = {
        "schema_version": "1.0.0",
        "artifact_type": "policy-decision",
        "id": artifact_id,
        "created_at": created_at,
        "actor": dict(actor),
        "run_id": run_id,
        "point": point,
        "decision": "allow" if result.allow else "deny",
        "reason_codes": list(result.reason_codes),
        "policy_bundle_version": result.policy_bundle_version,
        "input_digest": result.input_digest,
    }
    if links:
        document["links"] = [dict(link) for link in links]
    return document