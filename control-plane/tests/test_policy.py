"""Tests for the fail-closed OPA pre-tool-call policy client (M1).

TDD: these tests define the contract before the implementation exists.
"""

from __future__ import annotations

import json
import socket
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest

from sdlc.artifacts import find_repo_root, validate_artifact
from sdlc.policy import (
    REASON_ALLOWED,
    REASON_POLICY_MALFORMED,
    REASON_POLICY_UNAVAILABLE,
    PolicyClient,
    build_policy_decision,
    compute_input_digest,
)

REPO_ROOT = find_repo_root()

ACTOR = {"type": "agent", "id": "implementer", "role": "implementer"}
RUN_ID = "RUN-implementer-0001"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def _opa_stub(payload: bytes, status: int = 200) -> Iterator[str]:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
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
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _call(client: PolicyClient) -> Any:
    return client.evaluate(
        point="pre-tool-call",
        payload={"tool": "read_file", "path": ".env"},
    )


def test_evaluate_allows_when_opa_allows() -> None:
    body = json.dumps({"result": {"allow": True, "reason_codes": [REASON_ALLOWED]}}).encode()
    with _opa_stub(body) as url:
        result = _call(PolicyClient(base_url=url, bundle_version="0.1.0"))
    assert result.allow is True
    assert result.reason_codes == (REASON_ALLOWED,)
    assert result.policy_bundle_version == "0.1.0"
    assert len(result.input_digest) == 64


def test_evaluate_denies_with_reason_codes() -> None:
    body = json.dumps(
        {"result": {"allow": False, "reason_codes": ["TOOL_NOT_IN_ALLOWLIST"]}}
    ).encode()
    with _opa_stub(body) as url:
        result = _call(PolicyClient(base_url=url))
    assert result.allow is False
    assert result.reason_codes == ("TOOL_NOT_IN_ALLOWLIST",)


def test_fail_closed_on_transport_error() -> None:
    result = _call(PolicyClient(base_url=f"http://127.0.0.1:{_free_port()}", timeout=0.5))
    assert result.allow is False
    assert REASON_POLICY_UNAVAILABLE in result.reason_codes


def test_fail_closed_on_malformed_response() -> None:
    with _opa_stub(b"not-json") as url:
        result = _call(PolicyClient(base_url=url))
    assert result.allow is False
    assert REASON_POLICY_MALFORMED in result.reason_codes


def test_fail_closed_on_missing_result() -> None:
    with _opa_stub(b"{}") as url:
        result = _call(PolicyClient(base_url=url))
    assert result.allow is False
    assert REASON_POLICY_MALFORMED in result.reason_codes


def test_digest_is_stable_across_key_order() -> None:
    assert compute_input_digest({"b": 1, "a": {"y": 2, "x": 3}}) == compute_input_digest(
        {"a": {"x": 3, "y": 2}, "b": 1}
    )


def test_decision_document_validates_against_schema() -> None:
    body = json.dumps({"result": {"allow": True, "reason_codes": [REASON_ALLOWED]}}).encode()
    with _opa_stub(body) as url:
        result = _call(PolicyClient(base_url=url, bundle_version="0.1.0"))
    document = build_policy_decision(
        result,
        artifact_id="PD-0001",
        created_at="2026-09-22T00:00:00Z",
        actor=ACTOR,
        run_id=RUN_ID,
        point="pre-tool-call",
    )
    assert validate_artifact(document, REPO_ROOT) == []


def test_deny_decision_document_validates_against_schema() -> None:
    result = _call(PolicyClient(base_url=f"http://127.0.0.1:{_free_port()}", timeout=0.5))
    document = build_policy_decision(
        result,
        artifact_id="PD-0002",
        created_at="2026-09-22T00:00:00Z",
        actor=ACTOR,
        run_id=RUN_ID,
        point="pre-tool-call",
    )
    assert document["decision"] == "deny"
    assert validate_artifact(document, REPO_ROOT) == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))