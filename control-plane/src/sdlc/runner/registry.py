"""Ephemeral run registry issuing scoped capability tokens (M1, TASK-0003)."""

from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from .capability import (
    CAPABILITY_VALID,
    REASON_CAPABILITY_EXPIRED,
    REASON_RUN_FINISHED,
    REASON_RUN_UNKNOWN,
    REASON_SCOPE_MISMATCH,
    REASON_TOOL_MISMATCH,
    Capability,
    CapabilityCheck,
    decode_token,
    issue_token,
)

DEFAULT_TTL_SECONDS = 300


class RunUnknownError(ValueError):
    """Raised when a run id is not registered or already finished."""


@dataclass
class Run:
    """A single ephemeral agent run."""

    run_id: str
    actor: dict[str, Any]
    created_at: int
    finished: bool = False


class RunRegistry:
    """In-memory registry of runs; issues and verifies scoped capabilities."""

    def __init__(self, secret: bytes) -> None:
        self._secret = secret
        self._runs: dict[str, Run] = {}

    def start(self, actor: Mapping[str, Any]) -> Run:
        run = Run(run_id=f"RUN-{uuid4().hex}", actor=dict(actor), created_at=int(time.time()))
        self._runs[run.run_id] = run
        return run

    def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    def finish(self, run_id: str) -> None:
        run = self._runs.get(run_id)
        if run is None:
            raise RunUnknownError(run_id)
        run.finished = True

    def issue(
        self,
        run_id: str,
        *,
        tool: str,
        scope: str,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        now: int | None = None,
    ) -> str:
        run = self._runs.get(run_id)
        if run is None or run.finished:
            raise RunUnknownError(run_id)
        issued_at = int(time.time()) if now is None else now
        capability = Capability(
            run_id=run_id,
            tool=tool,
            scope=scope,
            expires_at=issued_at + ttl_seconds,
        )
        return issue_token(self._secret, capability)

    def check(
        self,
        token: str,
        *,
        tool: str,
        scope: str,
        now: int | None = None,
    ) -> CapabilityCheck:
        decoded = decode_token(self._secret, token)
        capability = decoded.capability
        if capability is None:
            return CapabilityCheck(False, decoded.error or REASON_RUN_UNKNOWN)
        run = self._runs.get(capability.run_id)
        if run is None:
            return self._reject(capability, REASON_RUN_UNKNOWN)
        if run.finished:
            return self._reject(capability, REASON_RUN_FINISHED)
        current = int(time.time()) if now is None else now
        if capability.expires_at < current:
            return self._reject(capability, REASON_CAPABILITY_EXPIRED)
        if capability.tool != tool:
            return self._reject(capability, REASON_TOOL_MISMATCH)
        if capability.scope != scope:
            return self._reject(capability, REASON_SCOPE_MISMATCH)
        return CapabilityCheck(True, CAPABILITY_VALID, capability.run_id, capability.tool, capability.scope)

    @staticmethod
    def _reject(capability: Capability, reason: str) -> CapabilityCheck:
        return CapabilityCheck(False, reason, capability.run_id, capability.tool, capability.scope)