"""Tests for the artifact-transition enforcement point (M2, TASK-0005).

The allow/deny rules live in Rego (``policies/artifact_transition.rego``, covered by
``opa test``); these tests cover the control-plane glue: input shape, OPA path, and the
emitted ``policy-decision`` artifact.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from sdlc.artifacts import find_repo_root, validate_artifact
from sdlc.policy import (
    PolicyClient,
    build_transition_decision,
    build_transition_input,
    evaluate_transition,
)

REPO_ROOT = find_repo_root()
ACTOR = {"type": "human", "id": "zarl3", "role": "reviewer"}
RUN_ID = "RUN-reviewer-0001"
NOW = "2026-10-01T00:00:00Z"


@contextmanager
def _opa_stub(payload: bytes, status: int = 200) -> Iterator[tuple[str, list[str]]]:
    paths: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            paths.append(self.path)
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, fmt: str, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", paths
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_build_transition_input_requires_core_fields() -> None:
    payload = build_transition_input(
        artifact_type="task", from_status="in_review", to_status="done", actor=ACTOR
    )
    assert payload == {
        "artifact_type": "task",
        "from_status": "in_review",
        "to_status": "done",
        "actor": ACTOR,
    }
    assert "now" not in payload
    assert "findings" not in payload
    assert "waivers" not in payload


def test_build_transition_input_includes_optional_context() -> None:
    payload = build_transition_input(
        artifact_type="task",
        from_status="in_review",
        to_status="done",
        actor=ACTOR,
        now=NOW,
        findings=[{"risk_id": "RISK-0003", "severity": "medium"}],
        waivers=[{"risk_id": "RISK-0003", "severity": "medium", "status": "active"}],
    )
    assert payload["now"] == NOW
    assert payload["findings"] == [{"risk_id": "RISK-0003", "severity": "medium"}]
    assert len(payload["waivers"]) == 1


def test_evaluate_transition_queries_artifact_transition_point() -> None:
    body = json.dumps({"result": {"allow": True, "reason_codes": ["ALLOWED"]}}).encode()
    with _opa_stub(body) as (url, paths):
        result = evaluate_transition(
            PolicyClient(base_url=url),
            artifact_type="task",
            from_status="todo",
            to_status="in_progress",
            actor=ACTOR,
        )
    assert result.allow is True
    assert paths == ["/v1/data/sdlc/artifact_transition/decision"]


def test_evaluate_transition_deny_builds_valid_decision_document() -> None:
    body = json.dumps({"result": {"allow": False, "reason_codes": ["BLOCKING_FINDING"]}}).encode()
    with _opa_stub(body) as (url, _):
        result = evaluate_transition(
            PolicyClient(base_url=url, bundle_version="0.1.0"),
            artifact_type="task",
            from_status="in_review",
            to_status="done",
            actor=ACTOR,
            now=NOW,
            findings=[{"risk_id": "RISK-0001", "severity": "high"}],
        )
    assert result.allow is False
    assert result.reason_codes == ("BLOCKING_FINDING",)

    document = build_transition_decision(
        result,
        artifact_id="PD-0001",
        created_at=NOW,
        actor=ACTOR,
        run_id=RUN_ID,
    )
    assert document["point"] == "artifact-transition"
    assert document["decision"] == "deny"
    assert validate_artifact(document, REPO_ROOT) == []


def test_policy_unavailable_fails_closed() -> None:
    result = evaluate_transition(
        PolicyClient(base_url="http://127.0.0.1:1", timeout=0.5),
        artifact_type="task",
        from_status="todo",
        to_status="in_progress",
        actor=ACTOR,
    )
    assert result.allow is False