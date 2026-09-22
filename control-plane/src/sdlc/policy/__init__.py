"""Fail-closed OPA pre-tool-call policy client and decision builder."""

from __future__ import annotations

from .artifact_transition import (
    POINT as ARTIFACT_TRANSITION_POINT,
)
from .artifact_transition import (
    build_transition_decision,
    build_transition_input,
    evaluate_transition,
)
from .client import (
    REASON_ALLOWED,
    REASON_DENIED,
    REASON_POLICY_MALFORMED,
    REASON_POLICY_UNAVAILABLE,
    PolicyClient,
    PolicyResult,
    compute_input_digest,
)
from .decision import build_policy_decision
from .pre_deployment import (
    POINT as PRE_DEPLOYMENT_POINT,
)
from .pre_deployment import (
    build_deployment_decision,
    build_deployment_input,
    evaluate_deployment,
)

__all__ = [
    "ARTIFACT_TRANSITION_POINT",
    "PRE_DEPLOYMENT_POINT",
    "REASON_ALLOWED",
    "REASON_DENIED",
    "REASON_POLICY_MALFORMED",
    "REASON_POLICY_UNAVAILABLE",
    "PolicyClient",
    "PolicyResult",
    "build_deployment_decision",
    "build_deployment_input",
    "build_policy_decision",
    "build_transition_decision",
    "build_transition_input",
    "compute_input_digest",
    "evaluate_deployment",
    "evaluate_transition",
]