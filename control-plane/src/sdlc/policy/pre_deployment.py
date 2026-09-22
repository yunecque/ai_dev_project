"""Pre-deployment enforcement point builder (ADR-0004/0005, M3 TASK-0001).

The allow/deny rules live in ``policies/pre_deployment.rego``; this module builds the OPA
input for an independent release gate and turns the decision into a ``policy-decision``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .client import PolicyClient, PolicyResult
from .decision import build_policy_decision

POINT = "pre-deployment"


def build_deployment_input(
    *,
    image: str,
    signature: Mapping[str, Any],
    sbom: Mapping[str, Any],
    provenance: Mapping[str, Any],
    policy_decisions: Sequence[Mapping[str, Any]],
    required_approver_role: str,
    approvals: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build the OPA input for a pre-deployment release gate."""
    return {
        "image": image,
        "signature": dict(signature),
        "sbom": dict(sbom),
        "provenance": dict(provenance),
        "policy_decisions": [dict(decision) for decision in policy_decisions],
        "required_approver_role": required_approver_role,
        "approvals": [dict(approval) for approval in approvals],
    }


def evaluate_deployment(policy: PolicyClient, **kwargs: Any) -> PolicyResult:
    """Evaluate a pre-deployment release gate against OPA (fail-closed)."""
    return policy.evaluate(point=POINT, payload=build_deployment_input(**kwargs))


def build_deployment_decision(
    result: PolicyResult,
    *,
    artifact_id: str,
    created_at: str,
    actor: Mapping[str, Any],
    run_id: str,
    links: Sequence[Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """Build a ``policy-decision`` artifact for the ``pre-deployment`` point."""
    return build_policy_decision(
        result,
        artifact_id=artifact_id,
        created_at=created_at,
        actor=actor,
        run_id=run_id,
        point=POINT,
        links=links,
    )