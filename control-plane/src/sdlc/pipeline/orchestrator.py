"""Pipeline orchestrator: idea -> specification -> threat-model -> plan -> task -> review (M6).

Each stage runs a role skill through the policy/capability-gated :class:`SkillRunner` and persists
the resulting canonical artifact through the gated ``write_artifact`` tool. A deterministic
``security-review`` is compiled from the threat model by the platform (not the LLM). The full chain
is audited with :func:`sdlc.traceability.trace_feature`.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..artifacts import validate_artifact
from ..evidence import EvidenceStore
from ..llm import LLMAdapter
from ..runner.executor import PolicyEvaluator, RunnerExecutor
from ..runner.registry import RunRegistry
from ..skills import (
    ContextInput,
    SkillRegistry,
    SkillRunner,
    SkillRunResult,
    add_links,
)
from ..tools import ArtifactStore
from ..traceability import Traceability, trace_feature

ARTIFACT_ID_PREFIX = {
    "idea": "IDEA",
    "specification": "SPEC",
    "threat-model": "TM",
    "plan": "PLAN",
    "task": "TASK",
    "review": "REV",
    "security-review": "SECREV",
}


class PipelineError(RuntimeError):
    """Raised when a stage is denied or produces an invalid artifact (fail-closed)."""


@dataclass(frozen=True)
class StageResult:
    """Audit trail for one pipeline stage."""

    stage: str
    artifact_type: str
    artifact_id: str
    decision: dict[str, Any]
    evidence: dict[str, Any]


@dataclass(frozen=True)
class PipelineResult:
    """The full outcome of a pipeline run."""

    feature_id: str
    run_id: str
    stages: tuple[StageResult, ...]
    artifacts: Mapping[str, dict[str, Any]]
    trace: Traceability


def build_security_review(
    *,
    feature_id: str,
    threat_model: Mapping[str, Any],
    artifact_id: str,
    created_at: str,
    actor: Mapping[str, Any],
    run_id: str,
    threat_model_href: str,
) -> dict[str, Any]:
    """Deterministically compile a security review from a threat model (trusted platform code)."""
    dispositions: list[dict[str, Any]] = []
    blocking = False
    for risk in threat_model.get("risks", []):
        severity = str(risk.get("severity", ""))
        verification = risk.get("verification_test")
        if severity in {"critical", "high"}:
            disposition = "mitigated" if verification else "open_blocking"
        elif severity == "medium":
            disposition = "waived_medium" if risk.get("waiver_id") else "open_blocking"
        else:
            disposition = "accepted_low"
        if disposition == "open_blocking":
            blocking = True
        entry: dict[str, Any] = {
            "risk_id": risk.get("id"),
            "severity": severity,
            "disposition": disposition,
        }
        if disposition == "mitigated" and verification:
            entry["verification_evidence"] = str(verification)
        dispositions.append(entry)
    return {
        "schema_version": "1.0.0",
        "artifact_type": "security-review",
        "id": artifact_id,
        "created_at": created_at,
        "created_by": actor,
        "run_id": run_id,
        "links": [{"rel": "threat", "href": threat_model_href}],
        "feature_id": feature_id,
        "threat_model_id": str(threat_model.get("id", "")),
        "verdict": "changes_requested" if blocking else "approved",
        "risk_dispositions": dispositions,
    }


class Pipeline:
    """Orchestrate the agent execution layer for a single feature."""

    def __init__(
        self,
        *,
        feature_id: str,
        run_id: str,
        actor: Mapping[str, Any],
        policy: PolicyEvaluator,
        capabilities: RunRegistry,
        skills: SkillRegistry,
        llm: LLMAdapter,
        executor: RunnerExecutor,
        store: ArtifactStore,
        evidence_store: EvidenceStore,
        repo_root: Path,
        schema_root: Path | None = None,
        href_prefix: str = "specs",
    ) -> None:
        self._feature_id = feature_id
        self._run_id = run_id
        self._actor = actor
        self._capabilities = capabilities
        self._skills = skills
        self._store = store
        self._repo_root = repo_root
        self._href_prefix = href_prefix
        self._executor = executor
        self._runner = SkillRunner(
            policy=policy,
            capabilities=capabilities,
            skills=skills,
            llm=llm,
            evidence_store=evidence_store,
            repo_root=schema_root,
        )
        self._created_at = ""
        self._counters: dict[str, int] = {}
        self._decision_seq = 0
        self._evidence_seq = 0
        self._written: dict[str, dict[str, Any]] = {}

    def run(self, idea: Mapping[str, Any], *, created_at: str) -> PipelineResult:
        self._created_at = created_at
        stages: list[StageResult] = []

        idea_id = str(idea.get("id") or self._artifact_id("idea"))
        stages.append(self._persist("idea", idea_id, dict(idea)))

        specification = self._skill(
            "grill",
            "specification",
            [ContextInput("idea", dict(idea))],
            {"feature_id": self._feature_id},
            links=[{"rel": "requirement", "href": self._href("idea", idea_id)}],
        )
        stages.append(specification[0])

        threat_model = self._skill(
            "grill-security",
            "threat-model",
            [ContextInput("specification", specification[1])],
            {"feature_id": self._feature_id},
            links=[{"rel": "requirement", "href": self._href("specification", specification[1]["id"])}],
        )
        stages.append(threat_model[0])

        plan = self._skill(
            "planner",
            "plan",
            [
                ContextInput("specification", specification[1]),
                ContextInput("threat-model", threat_model[1]),
            ],
            {"feature_id": self._feature_id},
            links=[{"rel": "threat", "href": self._href("threat-model", threat_model[1]["id"])}],
        )
        stages.append(plan[0])

        task = self._skill(
            "task-writer",
            "task",
            [
                ContextInput("specification", specification[1]),
                ContextInput("plan", plan[1]),
            ],
            {"feature_id": self._feature_id, "plan_id": plan[1]["id"]},
            links=[{"rel": "plan", "href": self._href("plan", plan[1]["id"])}],
        )
        stages.append(task[0])

        security_review = build_security_review(
            feature_id=self._feature_id,
            threat_model=threat_model[1],
            artifact_id=self._artifact_id("security-review"),
            created_at=created_at,
            actor={"type": "agent", "id": "security-reviewer", "role": "security-reviewer"},
            run_id=self._run_id,
            threat_model_href=self._href("threat-model", threat_model[1]["id"]),
        )
        stages.append(self._persist("security-review", security_review["id"], security_review))

        task_digest = hashlib.sha256(
            json.dumps(task[1], sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        review = self._skill(
            "reviewer",
            "review",
            [ContextInput("task", task[1])],
            {"feature_id": self._feature_id, "task_id": task[1]["id"], "subject_digest": task_digest},
            links=[{"rel": "task", "href": self._href("task", task[1]["id"])}],
        )
        stages.append(review[0])

        artifacts = dict(self._written)
        trace = trace_feature(
            self._repo_root,
            self._feature_id,
            artifacts={self._store.path(artifact_id): doc for artifact_id, doc in artifacts.items()},
        )
        return PipelineResult(
            feature_id=self._feature_id,
            run_id=self._run_id,
            stages=tuple(stages),
            artifacts=artifacts,
            trace=trace,
        )

    def _href(self, kind: str, artifact_id: str) -> str:
        return f"{self._href_prefix}/{artifact_id}.json"

    def _artifact_id(self, kind: str) -> str:
        next_value = self._counters.get(kind, 0) + 1
        self._counters[kind] = next_value
        return f"{ARTIFACT_ID_PREFIX[kind]}-{next_value:04d}"

    def _next_decision_id(self) -> str:
        self._decision_seq += 1
        return f"PD-{self._decision_seq:04d}"

    def _next_evidence_id(self) -> str:
        self._evidence_seq += 1
        return f"EV-{self._evidence_seq:04d}"

    def _skill(
        self,
        skill_name: str,
        kind: str,
        inputs: Sequence[ContextInput],
        bindings: Mapping[str, Any],
        *,
        links: Sequence[Mapping[str, str]],
    ) -> tuple[StageResult, dict[str, Any]]:
        skill = self._skills.get(skill_name)
        artifact_id = self._artifact_id(kind)
        token = self._capabilities.issue(self._run_id, tool=skill.tool_name, scope="skills")
        result: SkillRunResult = self._runner.run(
            run_id=self._run_id,
            token=token,
            skill_name=skill_name,
            inputs=inputs,
            bindings=bindings,
            artifact_id=artifact_id,
            created_at=self._created_at,
            decision_id=self._next_decision_id(),
            evidence_id=self._next_evidence_id(),
        )
        if not result.allowed or result.artifact is None:
            raise PipelineError(f"skill {skill_name} denied: {result.reason}")
        add_links(result.artifact, links)
        stage = self._persist(kind, artifact_id, result.artifact)
        return stage, result.artifact

    def _persist(self, kind: str, artifact_id: str, document: Mapping[str, Any]) -> StageResult:
        errors = validate_artifact(dict(document))
        if errors:
            raise PipelineError(f"invalid {kind} artifact: {'; '.join(errors)}")
        token = self._capabilities.issue(self._run_id, tool="write_artifact", scope="workspace")
        result = self._executor.execute(
            run_id=self._run_id,
            token=token,
            tool="write_artifact",
            args={"document": dict(document)},
            scope="workspace",
            created_at=self._created_at,
            decision_id=self._next_decision_id(),
            evidence_id=self._next_evidence_id(),
        )
        if not result.allowed:
            raise PipelineError(f"write_artifact denied for {artifact_id}: {result.reason}")
        self._written[artifact_id] = dict(document)
        return StageResult(kind, kind, artifact_id, result.decision, result.evidence)