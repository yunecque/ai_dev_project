"""Tests for the pre-deployment enforcement point (M3, TASK-0001).

The allow/deny rules live in Rego (``policies/pre_deployment.rego``, covered by ``opa test``);
here we cover the control-plane glue: input shape, OPA path, decision artifact, fail-closed.
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
    build_deployment_decision,
    build_deployment_input,
    evaluate_deployment,
)

REPO_ROOT = find_repo_root()
ACTOR = {"type": "human", "id": "zarl3", "role": "release-approver"}
RUN_ID = "RUN-deploy-0001"
NOW = "2026-10-01T00:00:00Z"
IMAGE = "ghcr.io/yunecque/ai_dev_project/domain:abc123"


def _valid_kwargs() -> dict[str, Any]:
    return {
        "image": IMAGE,
        "signature": {"verified": True, "issuer": "https://token.actions.githubusercontent.com", "identity": "repo:yunecque/ai_dev_project"},
        "sbom": {"present": True, "digest": "abc123"},
        "provenance": {"verified": True, "builder": "github-actions"},
        "policy_decisions": [
            {"point": "artifact-transition", "decision": "allow"},
            {"point": "pr-ci", "decision": "allow"},
        ],
        "required_approver_role": "release-approver",
        "approvals": [{"role": "release-approver", "actor": ACTOR}],
    }


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


def test_build_deployment_input_shape() -> None:
    payload = build_deployment_input(**_valid_kwargs())
    assert payload["image"] == IMAGE
    assert payload["signature"]["verified"] is True
    assert payload["required_approver_role"] == "release-approver"
    assert len(payload["policy_decisions"]) == 2
    assert payload["approvals"][0]["actor"] == ACTOR


def test_evaluate_deployment_queries_pre_deployment_point() -> None:
    body = json.dumps({"result": {"allow": True, "reason_codes": ["ALLOWED"]}}).encode()
    with _opa_stub(body) as (url, paths):
        result = evaluate_deployment(PolicyClient(base_url=url), **_valid_kwargs())
    assert result.allow is True
    assert paths == ["/v1/data/sdlc/pre_deployment/decision"]


def test_evaluate_deployment_deny_builds_valid_decision_document() -> None:
    body = json.dumps({"result": {"allow": False, "reason_codes": ["MISSING_SIGNATURE"]}}).encode()
    with _opa_stub(body) as (url, _):
        result = evaluate_deployment(
            PolicyClient(base_url=url, bundle_version="0.1.0"),
            **{**_valid_kwargs(), "signature": {"verified": False}},
        )
    assert result.allow is False
    assert result.reason_codes == ("MISSING_SIGNATURE",)

    document = build_deployment_decision(
        result, artifact_id="PD-0001", created_at=NOW, actor=ACTOR, run_id=RUN_ID
    )
    assert document["point"] == "pre-deployment"
    assert document["decision"] == "deny"
    assert validate_artifact(document, REPO_ROOT) == []


def test_policy_unavailable_fails_closed() -> None:
    result = evaluate_deployment(
        PolicyClient(base_url="http://127.0.0.1:1", timeout=0.5), **_valid_kwargs()
    )
    assert result.allow is False