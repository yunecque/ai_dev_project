"""Tests for the runner-executor gating and evidence (M6, TASK-0001).

The executor must fail closed: no policy, no capability, unknown tool, or a schema violation all
result in a deny. Every call (allow or deny) leaves a schema-valid policy-decision and
evidence-record.
"""

from __future__ import annotations

import json
import socket
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from sdlc.artifacts import find_repo_root, validate_artifact
from sdlc.evidence import EvidenceStore
from sdlc.policy import REASON_ALLOWED, REASON_POLICY_UNAVAILABLE, PolicyClient
from sdlc.runner import (
    REASON_EXECUTED,
    REASON_INVALID_ARGS,
    REASON_INVALID_RESULT,
    REASON_UNKNOWN_TOOL,
    Capability,
    RunnerExecutor,
    RunRegistry,
    issue_token,
)
from sdlc.tools import ToolRegistry, make_tool

REPO_ROOT = find_repo_root()
SECRET = b"executor-secret"
ACTOR = {"type": "agent", "id": "implementer", "role": "implementer"}
CREATED_AT = "2026-09-24T00:00:00Z"

ARGS_SCHEMA = {
    "type": "object",
    "required": ["path"],
    "properties": {"path": {"type": "string"}},
}
RESULT_SCHEMA = {
    "type": "object",
    "required": ["content"],
    "properties": {"content": {"type": "string"}, "path": {"type": "string"}},
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


def _read_handler(args: Mapping[str, Any]) -> Mapping[str, Any]:
    return {"content": "hello", "path": str(args.get("path", ""))}


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        make_tool(
            name="read_artifact",
            scope="workspace",
            description="read an artifact",
            handler=_read_handler,
            args_schema=ARGS_SCHEMA,
            result_schema=RESULT_SCHEMA,
        )
    )
    return registry


def _executor(policy: Any, capabilities: RunRegistry, tmp_path: Path) -> RunnerExecutor:
    return RunnerExecutor(
        policy=policy,
        capabilities=capabilities,
        tools=_registry(),
        evidence_store=EvidenceStore(tmp_path),
    )


def test_deny_when_policy_unavailable(tmp_path: Path) -> None:
    capabilities = RunRegistry(secret=SECRET)
    run = capabilities.start(ACTOR)
    token = capabilities.issue(run.run_id, tool="read_artifact", scope="workspace")
    policy = PolicyClient(base_url=f"http://127.0.0.1:{_free_port()}", timeout=0.5)
    result = _executor(policy, capabilities, tmp_path).execute(
        run_id=run.run_id,
        token=token,
        tool="read_artifact",
        args={"path": "specs/examples/idea.json"},
        scope="workspace",
        created_at=CREATED_AT,
        decision_id="PD-0001",
        evidence_id="EV-0001",
    )
    assert result.allowed is False
    assert result.reason == REASON_POLICY_UNAVAILABLE
    assert result.decision["decision"] == "deny"
    assert validate_artifact(result.decision, REPO_ROOT) == []
    assert validate_artifact(result.evidence, REPO_ROOT) == []


def test_deny_without_valid_capability(tmp_path: Path) -> None:
    capabilities = RunRegistry(secret=SECRET)
    run = capabilities.start(ACTOR)
    token = issue_token(
        b"another-secret",
        Capability(run_id=run.run_id, tool="read_artifact", scope="workspace", expires_at=2**31),
    )
    with _opa_stub(allow=True) as url:
        result = _executor(PolicyClient(base_url=url), capabilities, tmp_path).execute(
            run_id=run.run_id,
            token=token,
            tool="read_artifact",
            args={"path": "a"},
            scope="workspace",
            created_at=CREATED_AT,
            decision_id="PD-0002",
            evidence_id="EV-0002",
        )
    assert result.allowed is False
    assert result.decision["decision"] == "allow"
    assert validate_artifact(result.evidence, REPO_ROOT) == []


def test_allow_executes_and_records_evidence(tmp_path: Path) -> None:
    capabilities = RunRegistry(secret=SECRET)
    run = capabilities.start(ACTOR)
    token = capabilities.issue(run.run_id, tool="read_artifact", scope="workspace")
    with _opa_stub(allow=True) as url:
        result = _executor(PolicyClient(base_url=url), capabilities, tmp_path).execute(
            run_id=run.run_id,
            token=token,
            tool="read_artifact",
            args={"path": "specs/examples/idea.json"},
            scope="workspace",
            created_at=CREATED_AT,
            decision_id="PD-0003",
            evidence_id="EV-0003",
        )
    assert result.allowed is True
    assert result.reason == REASON_EXECUTED
    assert result.output == {"content": "hello", "path": "specs/examples/idea.json"}
    assert result.evidence["policy_decision_ref"] == "PD-0003"
    assert result.evidence["trust_tier"] == "untrusted"
    assert validate_artifact(result.decision, REPO_ROOT) == []
    assert validate_artifact(result.evidence, REPO_ROOT) == []


def test_unknown_tool_is_denied(tmp_path: Path) -> None:
    capabilities = RunRegistry(secret=SECRET)
    run = capabilities.start(ACTOR)
    token = capabilities.issue(run.run_id, tool="ghost", scope="workspace")
    with _opa_stub(allow=True) as url:
        result = _executor(PolicyClient(base_url=url), capabilities, tmp_path).execute(
            run_id=run.run_id,
            token=token,
            tool="ghost",
            args={},
            scope="workspace",
            created_at=CREATED_AT,
            decision_id="PD-0004",
            evidence_id="EV-0004",
        )
    assert result.allowed is False
    assert result.reason == REASON_UNKNOWN_TOOL
    assert result.output is None


def test_invalid_args_are_denied(tmp_path: Path) -> None:
    capabilities = RunRegistry(secret=SECRET)
    run = capabilities.start(ACTOR)
    token = capabilities.issue(run.run_id, tool="read_artifact", scope="workspace")
    with _opa_stub(allow=True) as url:
        result = _executor(PolicyClient(base_url=url), capabilities, tmp_path).execute(
            run_id=run.run_id,
            token=token,
            tool="read_artifact",
            args={},
            scope="workspace",
            created_at=CREATED_AT,
            decision_id="PD-0005",
            evidence_id="EV-0005",
        )
    assert result.allowed is False
    assert result.reason == REASON_INVALID_ARGS


def test_invalid_result_is_denied(tmp_path: Path) -> None:
    capabilities = RunRegistry(secret=SECRET)
    run = capabilities.start(ACTOR)
    token = capabilities.issue(run.run_id, tool="broken", scope="workspace")

    tools = ToolRegistry()
    tools.register(
        make_tool(
            name="broken",
            scope="workspace",
            description="returns the wrong shape",
            handler=lambda args: {"unexpected": True},
            args_schema=ARGS_SCHEMA,
            result_schema=RESULT_SCHEMA,
        )
    )
    with _opa_stub(allow=True) as url:
        executor = RunnerExecutor(
            policy=PolicyClient(base_url=url),
            capabilities=capabilities,
            tools=tools,
            evidence_store=EvidenceStore(tmp_path),
        )
        result = executor.execute(
            run_id=run.run_id,
            token=token,
            tool="broken",
            args={"path": "a"},
            scope="workspace",
            created_at=CREATED_AT,
            decision_id="PD-0006",
            evidence_id="EV-0006",
        )
    assert result.allowed is False
    assert result.reason == REASON_INVALID_RESULT