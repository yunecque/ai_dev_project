"""Tests for the minimal ephemeral-run registry and scoped capability tokens (M1).

TDD: define the runner contract before implementing it. The runner must fail closed:
any malformed, tampered, expired, mismatched, unknown, or revoked capability is invalid.
"""

from __future__ import annotations

import time

import pytest

from sdlc.runner import (
    CAPABILITY_VALID,
    REASON_CAPABILITY_EXPIRED,
    REASON_MALFORMED_TOKEN,
    REASON_RUN_FINISHED,
    REASON_RUN_UNKNOWN,
    REASON_SCOPE_MISMATCH,
    REASON_SIGNATURE_INVALID,
    REASON_TOOL_MISMATCH,
    RunRegistry,
    RunUnknownError,
)

SECRET = b"test-secret-not-for-production"
ACTOR = {"type": "agent", "id": "implementer", "role": "implementer"}


def _registry() -> RunRegistry:
    return RunRegistry(secret=SECRET)


def _run_with_token(
    registry: RunRegistry,
    *,
    tool: str = "read_file",
    scope: str = "workspace",
    ttl_seconds: int = 300,
    now: int | None = None,
) -> tuple[str, str]:
    run = registry.start(ACTOR)
    token = registry.issue(run.run_id, tool=tool, scope=scope, ttl_seconds=ttl_seconds, now=now)
    return run.run_id, token


def test_start_creates_runnable_id() -> None:
    run = _registry().start(ACTOR)
    assert run.run_id.startswith("RUN-")
    assert run.actor["id"] == "implementer"
    assert run.finished is False


def test_valid_capability_is_accepted() -> None:
    registry = _registry()
    run_id, token = _run_with_token(registry)
    check = registry.check(token, tool="read_file", scope="workspace")
    assert check.valid is True
    assert check.reason == CAPABILITY_VALID
    assert check.run_id == run_id


def test_tampered_token_is_rejected() -> None:
    registry = _registry()
    _, token = _run_with_token(registry)
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    check = registry.check(tampered, tool="read_file", scope="workspace")
    assert check.valid is False
    assert check.reason == REASON_SIGNATURE_INVALID


def test_token_from_different_secret_is_rejected() -> None:
    issuer = _registry()
    _, token = _run_with_token(issuer)
    other = RunRegistry(secret=b"a-different-secret")
    check = other.check(token, tool="read_file", scope="workspace")
    assert check.valid is False
    assert check.reason in {REASON_SIGNATURE_INVALID, REASON_RUN_UNKNOWN}


def test_expired_capability_is_rejected() -> None:
    registry = _registry()
    issued_at = int(time.time())
    _, token = _run_with_token(registry, ttl_seconds=1, now=issued_at)
    check = registry.check(token, tool="read_file", scope="workspace", now=issued_at + 60)
    assert check.valid is False
    assert check.reason == REASON_CAPABILITY_EXPIRED


def test_wrong_tool_is_rejected() -> None:
    registry = _registry()
    _, token = _run_with_token(registry, tool="read_file")
    check = registry.check(token, tool="write_file", scope="workspace")
    assert check.valid is False
    assert check.reason == REASON_TOOL_MISMATCH


def test_wrong_scope_is_rejected() -> None:
    registry = _registry()
    _, token = _run_with_token(registry, scope="workspace")
    check = registry.check(token, tool="read_file", scope="secrets")
    assert check.valid is False
    assert check.reason == REASON_SCOPE_MISMATCH


def test_finished_run_revokes_capability() -> None:
    registry = _registry()
    run_id, token = _run_with_token(registry)
    registry.finish(run_id)
    check = registry.check(token, tool="read_file", scope="workspace")
    assert check.valid is False
    assert check.reason == REASON_RUN_FINISHED


def test_unknown_run_is_rejected() -> None:
    issuer = _registry()
    _, token = _run_with_token(issuer)
    fresh = RunRegistry(secret=SECRET)
    check = fresh.check(token, tool="read_file", scope="workspace")
    assert check.valid is False
    assert check.reason == REASON_RUN_UNKNOWN


def test_malformed_token_is_rejected() -> None:
    registry = _registry()
    for bad in ["", "not-a-token", "v1.onlytwo", "v1..", "v2.abc.def"]:
        check = registry.check(bad, tool="read_file", scope="workspace")
        assert check.valid is False
        assert check.reason == REASON_MALFORMED_TOKEN


def test_issue_for_unknown_run_raises() -> None:
    registry = _registry()
    with pytest.raises(RunUnknownError):
        registry.issue("RUN-does-not-exist", tool="read_file", scope="workspace")