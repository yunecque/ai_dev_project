"""End-to-end pipeline orchestration test (M6, TASK-0006).

Runs the full ``idea -> ... -> review`` slice on a deterministic stub agent, asserting that every
stage is policy- and capability-gated, artifacts are schema-valid, and the traceability chain is
COMPLETE.
"""

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
from sdlc.llm import StubLLM
from sdlc.pipeline import Pipeline, PipelineError
from sdlc.policy import REASON_ALLOWED, PolicyClient
from sdlc.runner import RunnerExecutor, RunRegistry
from sdlc.skills import build_default_registry
from sdlc.tools import ArtifactStore, ToolRegistry, register_artifact_tools
from sdlc.traceability import CHAIN_ORDER

REPO_ROOT = find_repo_root()
SECRET = b"pipeline-secret"
ACTOR = {"type": "agent", "id": "pipeline", "role": "implementer"}
CREATED_AT = "2026-09-24T00:00:00Z"
FEATURE = "FEAT-0006"

IDEA = {
    "schema_version": "1.0.0",
    "artifact_type": "idea",
    "id": "IDEA-0001",
    "created_at": CREATED_AT,
    "created_by": {"type": "human", "id": "owner", "role": "author"},
    "title": "Agent execution layer slice",
    "problem": "The pipeline is manual",
    "actor_goal": "Automate idea -> review with policy and evidence",
    "source": {"kind": "issue", "ref": "issue#6", "trust_tier": "untrusted"},
}

OUTPUTS = {
    "grill": {
        "actor_goal": {"actors": ["user"], "goal": "create"},
        "scope_boundary": {"in_scope": ["api"], "out_of_scope": ["ui"]},
        "data_model": [],
        "api_contract": [],
        "state_lifecycle": [],
        "dependencies": [],
        "non_goals": [],
        "acceptance_criteria": [{"requirement_id": "REQ-0001", "criterion": "works"}],
    },
    "grill-security": {
        "data_flows": [],
        "risks": [
            {
                "id": "RISK-0001",
                "category": "spoofing",
                "scenario": "forged token",
                "severity": "high",
                "control_id": "CTRL-0001",
                "verification_test": "authorization_test.go",
            }
        ],
    },
    "planner": {
        "slices": [
            {
                "slice_id": "S1",
                "title": "slice",
                "requirement_ids": ["REQ-0001"],
                "control_ids": ["CTRL-0001"],
            }
        ]
    },
    "task-writer": {
        "title": "S1: slice",
        "requirement_ids": ["REQ-0001"],
        "control_ids": ["CTRL-0001"],
        "contract_changes": ["contracts/openapi/requests.yaml"],
        "code_changes": ["apps/gateway/server.go"],
        "tests": [{"kind": "unit", "ref": "a_test.go", "requirement_id": "REQ-0001"}],
    },
    "reviewer": {"verdict": "approved", "findings": []},
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


def _pipeline(policy: Any, tmp_path: Path) -> tuple[Pipeline, RunRegistry]:
    capabilities = RunRegistry(secret=SECRET)
    run = capabilities.start(ACTOR)
    store = ArtifactStore(tmp_path / "specs")
    evidence = EvidenceStore(tmp_path / "evidence")
    tools = ToolRegistry()
    register_artifact_tools(tools, store)
    executor = RunnerExecutor(
        policy=policy, capabilities=capabilities, tools=tools, evidence_store=evidence
    )
    pipeline = Pipeline(
        feature_id=FEATURE,
        run_id=run.run_id,
        actor=ACTOR,
        policy=policy,
        capabilities=capabilities,
        skills=build_default_registry(),
        llm=StubLLM({role: json.dumps(payload) for role, payload in OUTPUTS.items()}),
        executor=executor,
        store=store,
        evidence_store=evidence,
        repo_root=tmp_path,
    )
    return pipeline, capabilities


def test_full_pipeline_is_complete_and_auditable(tmp_path: Path) -> None:
    with _opa_stub(allow=True) as url:
        pipeline, _ = _pipeline(PolicyClient(base_url=url), tmp_path)
        result = pipeline.run(IDEA, created_at=CREATED_AT)

    assert result.trace.complete, result.trace
    assert result.trace.ordered_types == CHAIN_ORDER
    assert {stage.stage for stage in result.stages} == {
        "idea",
        "specification",
        "threat-model",
        "plan",
        "task",
        "security-review",
        "review",
    }
    for document in result.artifacts.values():
        assert validate_artifact(document, REPO_ROOT) == []
    for stage in result.stages:
        assert validate_artifact(stage.decision, REPO_ROOT) == []
        assert validate_artifact(stage.evidence, REPO_ROOT) == []
        assert stage.evidence["policy_decision_ref"] == stage.decision["id"]
    assert result.artifacts["TASK-0001"]["status"] == "todo"
    assert result.artifacts["SECREV-0001"]["verdict"] == "approved"


def test_policy_denial_aborts_pipeline(tmp_path: Path) -> None:
    with _opa_stub(allow=False) as url:
        pipeline, _ = _pipeline(PolicyClient(base_url=url), tmp_path)
        with pytest.raises(PipelineError):
            pipeline.run(IDEA, created_at=CREATED_AT)


def test_missing_capability_aborts_pipeline(tmp_path: Path) -> None:
    policy = PolicyClient(base_url=f"http://127.0.0.1:{_free_port()}", timeout=0.5)
    pipeline, _ = _pipeline(policy, tmp_path)
    with pytest.raises(PipelineError):
        pipeline.run(IDEA, created_at=CREATED_AT)