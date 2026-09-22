"""Negative pipeline: attempted bypasses must fail closed (M1, TASK-0012).

Models the composed guard for a tool call: an OPA decision gates the action first, and a
scoped capability token gates it second. Both must pass; any failure blocks the call.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import Any

from sdlc.evidence import EvidenceStore, SensitiveContentError, process_tool_output
from sdlc.policy import REASON_POLICY_UNAVAILABLE, PolicyClient
from sdlc.runner import RunRegistry
from sdlc.trust import TrustTier

SECRET = b"negative-pipeline-secret"
ACTOR = {"type": "agent", "id": "implementer", "role": "implementer"}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@dataclass(frozen=True)
class GuardOutcome:
    allowed: bool
    reason: str


def authorize_tool_call(
    policy: PolicyClient,
    registry: RunRegistry,
    *,
    run_id: str,
    token: str,
    tool: str,
    path: str,
    scope: str,
) -> GuardOutcome:
    decision = policy.evaluate(point="pre-tool-call", payload={"tool": tool, "path": path})
    if not decision.allow:
        return GuardOutcome(False, decision.reason_codes[0])
    check = registry.check(token, tool=tool, scope=scope)
    if not check.valid:
        return GuardOutcome(False, check.reason)
    return GuardOutcome(True, "ALLOWED")


def test_policy_unavailable_blocks_before_capability_check() -> None:
    policy = PolicyClient(base_url=f"http://127.0.0.1:{_free_port()}", timeout=0.5)
    registry = RunRegistry(secret=SECRET)
    run = registry.start(ACTOR)
    token = registry.issue(run.run_id, tool="read_file", scope="workspace")
    outcome = authorize_tool_call(
        policy, registry, run_id=run.run_id, token=token, tool="read_file", path="src/main.go", scope="workspace"
    )
    assert outcome.allowed is False
    assert outcome.reason == REASON_POLICY_UNAVAILABLE


def test_capability_for_different_tool_is_blocked() -> None:
    # OPA stub absent -> fail closed; here we only assert the capability layer independently.
    registry = RunRegistry(secret=SECRET)
    run = registry.start(ACTOR)
    token = registry.issue(run.run_id, tool="read_file", scope="workspace")
    check = registry.check(token, tool="write_file", scope="workspace")
    assert check.valid is False


def test_sensitive_tool_output_is_never_captured(tmp_path: Any) -> None:
    store = EvidenceStore(tmp_path)
    try:
        process_tool_output(
            "AWS_SECRET_ACCESS_KEY=leak",
            action="tool.bash.output",
            actor=ACTOR,
            run_id="RUN-negative-0001",
            artifact_id="EV-9001",
            created_at="2026-09-22T00:00:00Z",
            store=store,
            tier=TrustTier.SENSITIVE,
        )
    except SensitiveContentError:
        return
    raise AssertionError("sensitive content must not be captured into context")


def test_trusted_and_untrusted_sources_are_not_instructions() -> None:
    from sdlc.trust import can_use_as_instruction

    assert can_use_as_instruction(TrustTier.UNTRUSTED) is False
    assert can_use_as_instruction(TrustTier.SENSITIVE) is False