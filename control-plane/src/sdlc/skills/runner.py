"""Skill runner: policy + capability gating, LLM call, and evidence (M6, TASK-0002)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..artifacts import find_repo_root, validate_document
from ..evidence import EvidenceStore, process_tool_output
from ..llm import LLMAdapter, LLMRequest
from ..policy import build_policy_decision
from ..runner.executor import PolicyEvaluator
from ..runner.registry import RunRegistry, RunUnknownError
from ..trust import TrustTier
from .base import ContextInput, SkillError, build_context, extract_json
from .registry import SkillRegistry, UnknownSkillError

POLICY_POINT = "pre-tool-call"

REASON_COMPLETED = "COMPLETED"
REASON_UNKNOWN_SKILL = "UNKNOWN_SKILL"
REASON_MISSING_CONTEXT = "MISSING_CONTEXT"
REASON_INVALID_LLM_OUTPUT = "INVALID_LLM_OUTPUT"
REASON_SCHEMA_INVALID = "SCHEMA_INVALID"


@dataclass(frozen=True)
class SkillRunResult:
    """Outcome of a skill invocation with its audit artifacts."""

    allowed: bool
    reason: str
    decision: dict[str, Any]
    evidence: dict[str, Any]
    artifact: dict[str, Any] | None = None


class SkillRunner:
    """Run a role skill under the same fail-closed gating as the tool executor."""

    def __init__(
        self,
        *,
        policy: PolicyEvaluator,
        capabilities: RunRegistry,
        skills: SkillRegistry,
        llm: LLMAdapter,
        evidence_store: EvidenceStore,
        repo_root: Path | None = None,
    ) -> None:
        self._policy = policy
        self._capabilities = capabilities
        self._skills = skills
        self._llm = llm
        self._store = evidence_store
        self._repo_root = repo_root

    def run(
        self,
        *,
        run_id: str,
        token: str,
        skill_name: str,
        inputs: Sequence[ContextInput],
        bindings: Mapping[str, Any],
        artifact_id: str,
        created_at: str,
        decision_id: str,
        evidence_id: str,
        scope: str = "skills",
    ) -> SkillRunResult:
        run = self._capabilities.get(run_id)
        if run is None:
            raise RunUnknownError(run_id)
        actor = run.actor
        tool = f"skill.{skill_name}"

        policy_result = self._policy.evaluate(
            point=POLICY_POINT,
            payload={"tool": tool, "path": "", "scope": scope, "actor": actor},
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
            return self._deny(policy_result.reason_codes[0], decision, evidence_id, None, run_id, actor, created_at)

        check = self._capabilities.check(token, tool=tool, scope=scope)
        if not check.valid:
            return self._deny(check.reason, decision, evidence_id, None, run_id, actor, created_at)

        try:
            skill = self._skills.get(skill_name)
        except UnknownSkillError:
            return self._deny(REASON_UNKNOWN_SKILL, decision, evidence_id, None, run_id, actor, created_at)

        context = build_context(inputs)
        if any(key not in context for key in skill.context_keys):
            return self._deny(REASON_MISSING_CONTEXT, decision, evidence_id, None, run_id, actor, created_at)

        response = self._llm.complete(
            LLMRequest(role=skill.role, system_prompt=skill.system_prompt, context=context)
        )
        evidence = self._record(
            response.text,
            action=f"{skill.tool_name}.output",
            run_id=run_id,
            actor=actor,
            created_at=created_at,
            evidence_id=evidence_id,
            decision_id=str(decision["id"]),
        )
        try:
            content = extract_json(response.text)
        except SkillError:
            return SkillRunResult(False, REASON_INVALID_LLM_OUTPUT, decision, evidence, None)

        envelope: dict[str, Any] = {
            "artifact_id": artifact_id,
            "created_at": created_at,
            "actor": actor,
            "run_id": run_id,
            "bindings": dict(bindings),
        }
        artifact = skill.assemble(content, envelope)
        errors = validate_document(artifact, skill.output_schema, self._repo_root or find_repo_root())
        if errors:
            return SkillRunResult(False, REASON_SCHEMA_INVALID, decision, evidence, None)
        return SkillRunResult(True, REASON_COMPLETED, decision, evidence, artifact)

    def _deny(
        self,
        reason: str,
        decision: dict[str, Any],
        evidence_id: str,
        detail: str | None,
        run_id: str,
        actor: Mapping[str, Any],
        created_at: str,
    ) -> SkillRunResult:
        evidence = self._record(
            detail or reason,
            action="skill.denied",
            run_id=run_id,
            actor=actor,
            created_at=created_at,
            evidence_id=evidence_id,
            decision_id=str(decision["id"]),
        )
        return SkillRunResult(False, reason, decision, evidence, None)

    def _record(
        self,
        text: str,
        *,
        action: str,
        run_id: str,
        actor: Mapping[str, Any],
        created_at: str,
        evidence_id: str,
        decision_id: str,
    ) -> dict[str, Any]:
        outcome = process_tool_output(
            text,
            action=action,
            actor=actor,
            run_id=run_id,
            artifact_id=evidence_id,
            created_at=created_at,
            store=self._store,
            tier=TrustTier.UNTRUSTED,
            policy_decision_ref=decision_id,
        )
        return outcome.record