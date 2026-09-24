"""Runner-executor: execute allowlisted tools after policy and capability gating (M6, TASK-0001).

Every execution is fail-closed and auditable: a ``policy-decision`` records the OPA gate and an
``evidence-record`` records the call outcome. Gating order is OPA ``pre-tool-call`` first, then the
scoped capability, then the allowlisted tool lookup and schema validation. There is no shell
escape hatch; only registered tools run.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from ..evidence import EvidenceStore, process_tool_output
from ..evidence.pipeline import ToolOutputResult
from ..policy import PolicyResult, build_policy_decision
from ..runner.registry import RunRegistry, RunUnknownError
from ..tools import ToolRegistry, UnknownToolError, validate_instance

POLICY_POINT = "pre-tool-call"

REASON_EXECUTED = "EXECUTED"
REASON_UNKNOWN_TOOL = "UNKNOWN_TOOL"
REASON_INVALID_ARGS = "INVALID_TOOL_ARGS"
REASON_INVALID_RESULT = "INVALID_TOOL_RESULT"
REASON_EXECUTION_FAILED = "EXECUTION_FAILED"
REASON_SCOPE_MISMATCH = "SCOPE_MISMATCH"


class PolicyEvaluator(Protocol):
    """Structural interface satisfied by :class:`sdlc.policy.PolicyClient`."""

    def evaluate(self, *, point: str, payload: Mapping[str, Any]) -> PolicyResult: ...


@dataclass(frozen=True)
class ExecutionResult:
    """Outcome of a single tool invocation with its audit artifacts."""

    allowed: bool
    reason: str
    decision: dict[str, Any]
    evidence: dict[str, Any]
    output: Mapping[str, Any] | None = None


class RunnerExecutor:
    """Execute allowlisted tools under OPA + capability enforcement."""

    def __init__(
        self,
        *,
        policy: PolicyEvaluator,
        capabilities: RunRegistry,
        tools: ToolRegistry,
        evidence_store: EvidenceStore,
    ) -> None:
        self._policy = policy
        self._capabilities = capabilities
        self._tools = tools
        self._store = evidence_store

    def execute(
        self,
        *,
        run_id: str,
        token: str,
        tool: str,
        args: Mapping[str, Any],
        scope: str,
        created_at: str,
        decision_id: str,
        evidence_id: str,
        resource: str = "",
    ) -> ExecutionResult:
        run = self._capabilities.get(run_id)
        if run is None:
            raise RunUnknownError(run_id)
        actor = run.actor

        policy_result = self._policy.evaluate(
            point=POLICY_POINT,
            payload={"tool": tool, "path": resource, "scope": scope, "actor": actor},
        )
        decision = build_policy_decision(
            policy_result,
            artifact_id=decision_id,
            created_at=created_at,
            actor=actor,
            run_id=run_id,
            point=POLICY_POINT,
        )
        if not policy_result.allow:
            return self._deny(
                policy_result.reason_codes[0], tool, args, run_id, actor, created_at, decision, evidence_id
            )

        check = self._capabilities.check(token, tool=tool, scope=scope)
        if not check.valid:
            return self._deny(
                check.reason, tool, args, run_id, actor, created_at, decision, evidence_id
            )

        try:
            spec = self._tools.get(tool)
        except UnknownToolError:
            return self._deny(
                REASON_UNKNOWN_TOOL, tool, args, run_id, actor, created_at, decision, evidence_id
            )

        if spec.scope != scope:
            return self._deny(
                REASON_SCOPE_MISMATCH, tool, args, run_id, actor, created_at, decision, evidence_id
            )

        arg_errors = validate_instance(dict(args), spec.args_schema)
        if arg_errors:
            return self._deny(
                REASON_INVALID_ARGS, tool, args, run_id, actor, created_at, decision, evidence_id
            )

        try:
            output = spec.handler(args)
        except Exception:  # noqa: BLE001 - any handler failure must fail closed
            return self._deny(
                REASON_EXECUTION_FAILED, tool, args, run_id, actor, created_at, decision, evidence_id
            )
        result_errors = validate_instance(dict(output), spec.result_schema)
        if result_errors:
            return self._deny(
                REASON_INVALID_RESULT, tool, args, run_id, actor, created_at, decision, evidence_id
            )

        evidence = self._record(
            tool=tool,
            args=args,
            detail={"output": dict(output)},
            run_id=run_id,
            actor=actor,
            created_at=created_at,
            decision=decision,
            evidence_id=evidence_id,
        )
        return ExecutionResult(True, REASON_EXECUTED, decision, evidence, output)

    def _deny(
        self,
        reason: str,
        tool: str,
        args: Mapping[str, Any],
        run_id: str,
        actor: Mapping[str, Any],
        created_at: str,
        decision: dict[str, Any],
        evidence_id: str,
    ) -> ExecutionResult:
        evidence = self._record(
            tool=tool,
            args=args,
            detail={"denied": reason},
            run_id=run_id,
            actor=actor,
            created_at=created_at,
            decision=decision,
            evidence_id=evidence_id,
        )
        return ExecutionResult(False, reason, decision, evidence, None)

    def _record(
        self,
        *,
        tool: str,
        args: Mapping[str, Any],
        detail: Mapping[str, Any],
        run_id: str,
        actor: Mapping[str, Any],
        created_at: str,
        decision: dict[str, Any],
        evidence_id: str,
    ) -> dict[str, Any]:
        payload = json.dumps(
            {"tool": tool, "args": dict(args), "detail": dict(detail)},
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        )
        outcome: ToolOutputResult = process_tool_output(
            payload,
            action=f"tool.{tool}",
            actor=actor,
            run_id=run_id,
            artifact_id=evidence_id,
            created_at=created_at,
            store=self._store,
            policy_decision_ref=str(decision["id"]),
        )
        return outcome.record