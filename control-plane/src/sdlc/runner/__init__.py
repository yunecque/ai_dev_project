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
from .executor import (
    POLICY_POINT,
    REASON_EXECUTED,
    REASON_EXECUTION_FAILED,
    REASON_INVALID_ARGS,
    REASON_INVALID_RESULT,
    REASON_UNKNOWN_TOOL,
    ExecutionResult,
    PolicyEvaluator,
    RunnerExecutor,
)
from .executor import (
    REASON_SCOPE_MISMATCH as REASON_EXECUTION_SCOPE_MISMATCH,
)
from .registry import DEFAULT_TTL_SECONDS, Run, RunRegistry, RunUnknownError

__all__ = [
    "CAPABILITY_VALID",
    "DEFAULT_TTL_SECONDS",
    "POLICY_POINT",
    "REASON_CAPABILITY_EXPIRED",
    "REASON_EXECUTED",
    "REASON_EXECUTION_FAILED",
    "REASON_EXECUTION_SCOPE_MISMATCH",
    "REASON_INVALID_ARGS",
    "REASON_INVALID_RESULT",
    "REASON_MALFORMED_TOKEN",
    "REASON_RUN_FINISHED",
    "REASON_RUN_UNKNOWN",
    "REASON_SCOPE_MISMATCH",
    "REASON_SIGNATURE_INVALID",
    "REASON_TOOL_MISMATCH",
    "REASON_UNKNOWN_TOOL",
    "Capability",
    "CapabilityCheck",
    "DecodeResult",
    "ExecutionResult",
    "PolicyEvaluator",
    "Run",
    "RunRegistry",
    "RunUnknownError",
    "RunnerExecutor",
    "decode_token",
    "issue_token",
]