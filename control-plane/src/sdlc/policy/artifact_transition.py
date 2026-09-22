"""Artifact-transition enforcement point builder (ADR-0004, M2 TASK-0005).

The actual allow/deny rules live in ``policies/artifact_transition.rego``; this module
builds the OPA input and turns the decision into a ``policy-decision`` artifact.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .client import PolicyClient, PolicyResult
from .decision import build_policy_decision

POINT = "artifact-transition"


def build_transition_input(
    *,
    artifact_type: str,
    from_status: str,
    to_status: str,
    actor: Mapping[str, Any],
    now: str | None = None,
    findings: Sequence[Mapping[str, Any]] | None = None,
    waivers: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the OPA input for an artifact lifecycle transition."""
    payload: dict[str, Any] = {
        "artifact_type": artifact_type,
        "from_status": from_status,
        "to_status": to_status,
        "actor": dict(actor),
    }
    if now is not None:
        payload["now"] = now
    if findings:
        payload["findings"] = [dict(finding) for finding in findings]
    if waivers:
        payload["waivers"] = [dict(waiver) for waiver in waivers]
    return payload


def evaluate_transition(policy: PolicyClient, **kwargs: Any) -> PolicyResult:
    """Evaluate an artifact transition against OPA (fail-closed)."""
    return policy.evaluate(point=POINT, payload=build_transition_input(**kwargs))


def build_transition_decision(
    result: PolicyResult,
    *,
    artifact_id: str,
    created_at: str,
    actor: Mapping[str, Any],
    run_id: str,
    links: Sequence[Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    """Build a ``policy-decision`` artifact for the ``artifact-transition`` point."""
    return build_policy_decision(
        result,
        artifact_id=artifact_id,
        created_at=created_at,
        actor=actor,
        run_id=run_id,
        point=POINT,
        links=links,
    )