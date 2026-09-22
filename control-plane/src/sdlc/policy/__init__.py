"""Fail-closed OPA pre-tool-call policy client and decision builder."""

from __future__ import annotations

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
    "REASON_ALLOWED",
    "REASON_DENIED",
    "REASON_POLICY_MALFORMED",
    "REASON_POLICY_UNAVAILABLE",
    "PolicyClient",
    "PolicyResult",
    "build_policy_decision",
    "compute_input_digest",
]