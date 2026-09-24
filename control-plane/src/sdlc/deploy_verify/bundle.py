"""Build a content-addressed evidence bundle from a release candidate (M3, TASK-0002).

The bundle is a canonical manifest: every release evidence item (signature, SBOM, provenance,
prior policy decisions, approvals) is reduced to a kind/ref/digest triple. ``bundle_digest``
commits to the image, the candidate digest, and the ordered item list.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .candidate import sha256_digest

BUNDLE_TYPE = "evidence-bundle"
OBJECT_ITEMS = ("signature", "sbom", "provenance")


def _collect_items(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for kind in OBJECT_ITEMS:
        value = candidate.get(kind)
        if isinstance(value, Mapping):
            items.append({"kind": kind, "ref": f"candidate:{kind}", "digest": sha256_digest(value)})
    decisions = candidate.get("policy_decisions", [])
    for decision in decisions:
        if isinstance(decision, Mapping):
            point = str(decision.get("point", ""))
            items.append(
                {"kind": "policy-decision", "ref": point, "digest": sha256_digest(decision)}
            )
    approvals = candidate.get("approvals", [])
    for approval in approvals:
        if isinstance(approval, Mapping):
            actor = approval.get("actor", {})
            actor_id = str(actor.get("id", "")) if isinstance(actor, Mapping) else ""
            ref = f"{approval.get('role', '')}:{actor_id}"
            items.append({"kind": "approval", "ref": ref, "digest": sha256_digest(approval)})
    return items


def bundle_digest(image: str, candidate_digest: str, items: Sequence[Mapping[str, Any]]) -> str:
    """Commit to the image, candidate digest, and ordered item list."""
    return sha256_digest(
        {"image": image, "candidate_digest": candidate_digest, "items": list(items)}
    )


def build_evidence_bundle(
    *,
    artifact_id: str,
    created_at: str,
    actor: Mapping[str, Any],
    run_id: str,
    candidate: Mapping[str, Any],
    links: Sequence[Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """Return a document validating against contracts/schemas/evidence-bundle.schema.json."""
    image = str(candidate.get("image", ""))
    candidate_digest = sha256_digest(candidate)
    items = _collect_items(candidate)
    document: dict[str, Any] = {
        "schema_version": "1.0.0",
        "artifact_type": BUNDLE_TYPE,
        "id": artifact_id,
        "created_at": created_at,
        "actor": dict(actor),
        "run_id": run_id,
        "image": image,
        "candidate_digest": candidate_digest,
        "bundle_digest": bundle_digest(image, candidate_digest, items),
        "items": items,
    }
    if links:
        document["links"] = [dict(link) for link in links]
    return document
