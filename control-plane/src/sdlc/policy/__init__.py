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

__all__ = [
    "ARTIFACT_TRANSITION_POINT",
    "REASON_ALLOWED",
    "REASON_DENIED",
    "REASON_POLICY_MALFORMED",
    "REASON_POLICY_UNAVAILABLE",
    "PolicyClient",
    "PolicyResult",
    "build_policy_decision",
    "build_transition_decision",
    "build_transition_input",
    "compute_input_digest",
    "evaluate_transition",
]