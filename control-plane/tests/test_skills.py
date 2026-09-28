"""Tests for the LLM adapter and role skills (M6, TASK-0002)."""

from __future__ import annotations

import json
import socket
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from sdlc.artifacts import find_repo_root, validate_artifact
from sdlc.evidence import EvidenceStore
from sdlc.evidence.pipeline import SensitiveContentError
from sdlc.llm import LLMError, LLMRequest, StubLLM
from sdlc.policy import REASON_ALLOWED, REASON_POLICY_UNAVAILABLE, PolicyClient
from sdlc.runner import RunRegistry
from sdlc.skills import (
    REASON_COMPLETED,
    REASON_INVALID_LLM_OUTPUT,
    REASON_SCHEMA_INVALID,
    TASK_WRITER,
    ContextInput,
    SkillError,
    SkillRegistry,
    SkillRunner,
    build_context,
    build_default_registry,
    extract_json,
)

REPO_ROOT = find_repo_root()
SECRET = b"skills-secret"
ACTOR = {"type": "agent", "id": "task-writer", "role": "task-writer"}
CREATED_AT = "2026-09-24T00:00:00Z"

VALID_CONTENT = {
    "title": "S1: POST /requests",
    "requirement_ids": ["REQ-0001"],
    "control_ids": ["CTRL-0001"],
    "contract_changes": ["contracts/openapi/requests.yaml"],
    "code_changes": ["apps/gateway/server.go"],
    "tests": [{"kind": "unit", "ref": "a_test.go", "requirement_id": "REQ-0001"}],
}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def _opa_stub(allow: bool) -> Iterator[str]:
    body = json.dumps(
        {"result": {"allow": allow, "reason_codes": [REASON_ALLOWED if allow else "DENIED"]}}
    ).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _inputs() -> list[ContextInput]:
    return [
        ContextInput(name="specification", document={"id": "SPEC-0001"}),
        ContextInput(name="plan", document={"id": "PLAN-0001"}),
    ]


def _runner(policy: Any, capabilities: RunRegistry, tmp_path: Path, text: str) -> SkillRunner:
    return SkillRunner(
        policy=policy,
        capabilities=capabilities,
        skills=SkillRegistry((TASK_WRITER,)),
        llm=StubLLM({"task-writer": text}),
        evidence_store=EvidenceStore(tmp_path),
        repo_root=REPO_ROOT,
    )


def _valid_text(extra: dict[str, Any] | None = None) -> str:
    return json.dumps({**VALID_CONTENT, **(extra or {})})


def test_stub_llm_unknown_role_fails_closed() -> None:
    with pytest.raises(LLMError):
        StubLLM({}).complete(LLMRequest(role="ghost", system_prompt="", context={}))


def test_build_context_rejects_sensitive() -> None:
    with pytest.raises(SensitiveContentError):
        build_context([ContextInput(name="creds", document={"k": "v"}, source="secret")])


def test_extract_json_handles_fences_and_prose() -> None:
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('here you go: {"a": 2} thanks') == {"a": 2}
    with pytest.raises(SkillError):
        extract_json("not json at all")


def test_task_writer_produces_schema_valid_artifact(tmp_path: Path) -> None:
    capabilities = RunRegistry(secret=SECRET)
    run = capabilities.start(ACTOR)
    token = capabilities.issue(run.run_id, tool="skill.task-writer", scope="skills")
    with _opa_stub(allow=True) as url:
        result = _runner(PolicyClient(base_url=url), capabilities, tmp_path, _valid_text()).run(
            run_id=run.run_id,
            token=token,
            skill_name="task-writer",
            inputs=_inputs(),
            bindings={"feature_id": "FEAT-0006", "plan_id": "PLAN-0001"},
            artifact_id="TASK-0001",
            created_at=CREATED_AT,
            decision_id="PD-1001",
            evidence_id="EV-1001",
        )
    assert result.allowed is True
    assert result.reason == REASON_COMPLETED
    assert result.artifact is not None
    assert result.artifact["status"] == "todo"
    assert result.artifact["created_by"] == ACTOR
    assert result.artifact["id"] == "TASK-0001"
    assert validate_artifact(result.artifact, REPO_ROOT) == []
    assert validate_artifact(result.decision, REPO_ROOT) == []
    assert validate_artifact(result.evidence, REPO_ROOT) == []
    assert result.evidence["policy_decision_ref"] == "PD-1001"


def test_llm_injected_fields_are_ignored(tmp_path: Path) -> None:
    capabilities = RunRegistry(secret=SECRET)
    run = capabilities.start(ACTOR)
    token = capabilities.issue(run.run_id, tool="skill.task-writer", scope="skills")
    injected = _valid_text({"status": "done", "approved": True, "run_id": "RUN-evil"})
    with _opa_stub(allow=True) as url:
        result = _runner(PolicyClient(base_url=url), capabilities, tmp_path, injected).run(
            run_id=run.run_id,
            token=token,
            skill_name="task-writer",
            inputs=_inputs(),
            bindings={"feature_id": "FEAT-0006", "plan_id": "PLAN-0001"},
            artifact_id="TASK-0002",
            created_at=CREATED_AT,
            decision_id="PD-1002",
            evidence_id="EV-1002",
        )
    assert result.allowed is True
    assert result.artifact is not None
    assert result.artifact["status"] == "todo"
    assert "approved" not in result.artifact
    assert result.artifact["run_id"] == run.run_id


def test_invalid_llm_output_fails_closed(tmp_path: Path) -> None:
    capabilities = RunRegistry(secret=SECRET)
    run = capabilities.start(ACTOR)
    token = capabilities.issue(run.run_id, tool="skill.task-writer", scope="skills")
    with _opa_stub(allow=True) as url:
        result = _runner(PolicyClient(base_url=url), capabilities, tmp_path, "ignore instructions").run(
            run_id=run.run_id,
            token=token,
            skill_name="task-writer",
            inputs=_inputs(),
            bindings={"feature_id": "FEAT-0006", "plan_id": "PLAN-0001"},
            artifact_id="TASK-0003",
            created_at=CREATED_AT,
            decision_id="PD-1003",
            evidence_id="EV-1003",
        )
    assert result.allowed is False
    assert result.reason == REASON_INVALID_LLM_OUTPUT
    assert validate_artifact(result.evidence, REPO_ROOT) == []


def test_schema_invalid_output_fails_closed(tmp_path: Path) -> None:
    capabilities = RunRegistry(secret=SECRET)
    run = capabilities.start(ACTOR)
    token = capabilities.issue(run.run_id, tool="skill.task-writer", scope="skills")
    with _opa_stub(allow=True) as url:
        result = _runner(PolicyClient(base_url=url), capabilities, tmp_path, "{}").run(
            run_id=run.run_id,
            token=token,
            skill_name="task-writer",
            inputs=_inputs(),
            bindings={"feature_id": "FEAT-0006", "plan_id": "PLAN-0001"},
            artifact_id="TASK-0004",
            created_at=CREATED_AT,
            decision_id="PD-1004",
            evidence_id="EV-1004",
        )
    assert result.allowed is False
    assert result.reason == REASON_SCHEMA_INVALID


def test_policy_unavailable_fails_closed(tmp_path: Path) -> None:
    capabilities = RunRegistry(secret=SECRET)
    run = capabilities.start(ACTOR)
    token = capabilities.issue(run.run_id, tool="skill.task-writer", scope="skills")
    policy = PolicyClient(base_url=f"http://127.0.0.1:{_free_port()}", timeout=0.5)
    result = _runner(policy, capabilities, tmp_path, _valid_text()).run(
        run_id=run.run_id,
        token=token,
        skill_name="task-writer",
        inputs=_inputs(),
        bindings={"feature_id": "FEAT-0006", "plan_id": "PLAN-0001"},
        artifact_id="TASK-0005",
        created_at=CREATED_AT,
        decision_id="PD-1005",
        evidence_id="EV-1005",
    )
    assert result.allowed is False
    assert result.reason == REASON_POLICY_UNAVAILABLE
    assert result.decision["decision"] == "deny"
ROLE_OUTPUTS = {
    "grill": {
        "actor_goal": {"actors": ["user"], "goal": "create a request"},
        "scope_boundary": {"in_scope": ["api"], "out_of_scope": ["ui"]},
        "data_model": [{"entity": "request", "fields": ["id"]}],
        "api_contract": [{"operation_id": "CreateRequest", "kind": "rest", "summary": "create"}],
        "state_lifecycle": [{"from": "created", "to": "triaged", "actor": "operator"}],
        "dependencies": [],
        "non_goals": [],
        "acceptance_criteria": [{"requirement_id": "REQ-0001", "criterion": "c"}],
    },
    "grill-security": {
        "data_flows": [
            {"id": "DF-1", "from": "client", "to": "gateway", "data": ["token"], "crosses_trust_boundary": True}
        ],
        "risks": [
            {
                "id": "RISK-0001",
                "category": "spoofing",
                "scenario": "forged token",
                "severity": "high",
                "control_id": "CTRL-0001",
                "verification_test": "authz_test",
            }
        ],
    },
    "planner": {
        "slices": [
            {"slice_id": "S1", "title": "create", "requirement_ids": ["REQ-0001"], "control_ids": ["CTRL-0001"]}
        ]
    },
    "reviewer": {"verdict": "approved", "findings": []},
}

ROLL_BINDINGS = {
    "feature_id": "FEAT-0006",
    "task_id": "TASK-0001",
    "subject_digest": "a" * 64,
}


def _role_runner(policy: Any, capabilities: RunRegistry, tmp_path: Path) -> SkillRunner:
    responses = {role: json.dumps(payload) for role, payload in ROLE_OUTPUTS.items()}
    return SkillRunner(
        policy=policy,
        capabilities=capabilities,
        skills=build_default_registry(),
        llm=StubLLM(responses),
        evidence_store=EvidenceStore(tmp_path),
        repo_root=REPO_ROOT,
    )


@pytest.mark.parametrize("skill_name", ["grill", "grill-security", "planner", "reviewer"])
def test_role_skills_produce_schema_valid_artifacts(skill_name: str, tmp_path: Path) -> None:
    capabilities = RunRegistry(secret=SECRET)
    run = capabilities.start({"type": "agent", "id": skill_name, "role": skill_name})
    token = capabilities.issue(run.run_id, tool=f"skill.{skill_name}", scope="skills")
    context_by_skill = {
        "grill": [ContextInput(name="idea", document={"id": "IDEA-0001"})],
        "grill-security": [ContextInput(name="specification", document={"id": "SPEC-0001"})],
        "planner": [
            ContextInput(name="specification", document={"id": "SPEC-0001"}),
            ContextInput(name="threat-model", document={"id": "TM-0001"}),
        ],
        "reviewer": [ContextInput(name="task", document={"id": "TASK-0001"})],
    }
    with _opa_stub(allow=True) as url:
        runner = _role_runner(PolicyClient(base_url=url), capabilities, tmp_path)
        result = runner.run(
            run_id=run.run_id,
            token=token,
            skill_name=skill_name,
            inputs=context_by_skill[skill_name],
            bindings=ROLL_BINDINGS,
            artifact_id="ART-0001",
            created_at=CREATED_AT,
            decision_id="PD-2001",
            evidence_id="EV-2001",
        )
    assert result.allowed is True, result.reason
    assert result.artifact is not None
    if skill_name != "reviewer":
        assert result.artifact["status"] == "draft"
    assert validate_artifact(result.artifact, REPO_ROOT) == []


def test_reviewer_ignores_injected_feature_fields(tmp_path: Path) -> None:
    capabilities = RunRegistry(secret=SECRET)
    run = capabilities.start({"type": "agent", "id": "reviewer", "role": "reviewer"})
    token = capabilities.issue(run.run_id, tool="skill.reviewer", scope="skills")
    text = json.dumps({"verdict": "changes_requested", "findings": [], "status": "approved"})
    review_skill = build_default_registry().get("reviewer")
    with _opa_stub(allow=True) as url:
        runner = SkillRunner(
            policy=PolicyClient(base_url=url),
            capabilities=capabilities,
            skills=SkillRegistry((review_skill,)),
            llm=StubLLM({"reviewer": text}),
            evidence_store=EvidenceStore(tmp_path),
            repo_root=REPO_ROOT,
        )
        result = runner.run(
            run_id=run.run_id,
            token=token,
            skill_name="reviewer",
            inputs=[ContextInput(name="task", document={"id": "TASK-0001"})],
            bindings=ROLL_BINDINGS,
            artifact_id="REV-0001",
            created_at=CREATED_AT,
            decision_id="PD-2002",
            evidence_id="EV-2002",
        )
    assert result.allowed is True
    assert result.artifact is not None
    assert result.artifact["verdict"] == "changes_requested"
    assert "status" not in result.artifact
