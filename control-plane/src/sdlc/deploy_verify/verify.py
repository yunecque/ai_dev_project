"""Independent pre-deployment release verification (M3, TASK-0002).

Composes the M3 TASK-0001 enforcement point: gather release evidence into a content-addressed
bundle, evaluate the ``pre-deployment`` OPA policy (fail-closed), and emit the corresponding
``policy-decision``. The bundle and decision are returned; persisting them is the caller's job.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..policy import PolicyClient, build_deployment_decision, evaluate_deployment
from .bundle import build_evidence_bundle
from .candidate import validate_candidate


@dataclass(frozen=True)
class ReleaseVerification:
    """Outcome of an independent pre-deployment verification."""

    allow: bool
    reason_codes: tuple[str, ...]
    decision: dict[str, Any]
    bundle: dict[str, Any]


def _deployment_input(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "image": candidate["image"],
        "signature": candidate["signature"],
        "sbom": candidate["sbom"],
        "provenance": candidate["provenance"],
        "policy_decisions": candidate["policy_decisions"],
        "required_approver_role": candidate["required_approver_role"],
        "approvals": candidate["approvals"],
    }


def verify_release(
    policy: PolicyClient,
    candidate: Mapping[str, Any],
    *,
    bundle_id: str,
    decision_id: str,
    created_at: str,
    actor: Mapping[str, Any],
    run_id: str,
    repo_root: Path | None = None,
) -> ReleaseVerification:
    """Verify a release candidate and return its evidence bundle and policy decision."""
    validate_candidate(candidate, repo_root)
    bundle = build_evidence_bundle(
        artifact_id=bundle_id,
        created_at=created_at,
        actor=actor,
        run_id=run_id,
        candidate=candidate,
    )
    result = evaluate_deployment(policy, **_deployment_input(candidate))
    decision = build_deployment_decision(
        result,
        artifact_id=decision_id,
        created_at=created_at,
        actor=actor,
        run_id=run_id,
        links=[{"rel": "evidence", "href": bundle_id}],
    )
    bundle["policy_decision_ref"] = decision_id
    return ReleaseVerification(result.allow, result.reason_codes, decision, bundle)
