"""Ephemeral run registry and scoped capability tokens (M1, TASK-0003)."""

from __future__ import annotations

from .capability import (
    CAPABILITY_VALID,
    REASON_CAPABILITY_EXPIRED,
    REASON_MALFORMED_TOKEN,
    REASON_RUN_FINISHED,
    REASON_RUN_UNKNOWN,
    REASON_SCOPE_MISMATCH,
    REASON_SIGNATURE_INVALID,
    REASON_TOOL_MISMATCH,
    Capability,
    CapabilityCheck,
    DecodeResult,
    decode_token,
    issue_token,
)
from .registry import DEFAULT_TTL_SECONDS, Run, RunRegistry, RunUnknownError

__all__ = [
    "CAPABILITY_VALID",
    "DEFAULT_TTL_SECONDS",
    "REASON_CAPABILITY_EXPIRED",
    "REASON_MALFORMED_TOKEN",
    "REASON_RUN_FINISHED",
    "REASON_RUN_UNKNOWN",
    "REASON_SCOPE_MISMATCH",
    "REASON_SIGNATURE_INVALID",
    "REASON_TOOL_MISMATCH",
    "Capability",
    "CapabilityCheck",
    "DecodeResult",
    "Run",
    "RunRegistry",
    "RunUnknownError",
    "decode_token",
    "issue_token",
]