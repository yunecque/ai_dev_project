"""Tests for the independent pre-deployment release verification (M3, TASK-0002).

The allow/deny rules live in Rego (``policies/pre_deployment.rego``, covered by ``opa test``);
here we cover the control-plane glue: candidate schema, content-addressed bundle, decision
artifact, fail-closed behavior, and the CLI.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from sdlc.artifacts import find_repo_root, validate_artifact
from sdlc.cli import main
from sdlc.deploy_verify import (
    CandidateError,
    build_evidence_bundle,
    bundle_digest,
    load_candidate,
    verify_release,
)
from sdlc.policy import PolicyClient

REPO_ROOT = find_repo_root()
EXAMPLE = REPO_ROOT / "specs" / "examples" / "release-candidate.json"
ACTOR = {"type": "ci", "id": "deploy-verify", "role": "release-approver"}
RUN_ID = "RUN-deploy-verify-0001"
NOW = "2026-10-01T00:00:00Z"


def _candidate() -> dict[str, Any]:
    return load_candidate(EXAMPLE, REPO_ROOT)


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


def _allow_body() -> bytes:
    return json.dumps({"result": {"allow": True, "reason_codes": ["ALLOWED"]}}).encode()


def _deny_body() -> bytes:
    return json.dumps({"result": {"allow": False, "reason_codes": ["MISSING_SBOM"]}}).encode()


def _verify(url: str, *, bundle_version: str = "0.1.0") -> Any:
    return verify_release(
        PolicyClient(base_url=url, bundle_version=bundle_version),
        _candidate(),
        bundle_id="EB-0001",
        decision_id="PD-0001",
        created_at=NOW,
        actor=ACTOR,
        run_id=RUN_ID,
        repo_root=REPO_ROOT,
    )


def test_example_candidate_is_valid() -> None:
    candidate = _candidate()
    assert candidate["artifact_type"] == "release-candidate"
    assert candidate["image"].startswith("ghcr.io/")


def test_load_candidate_rejects_missing_field(tmp_path: Path) -> None:
    candidate = _candidate()
    del candidate["provenance"]
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(candidate), encoding="utf-8")
    with pytest.raises(CandidateError):
        load_candidate(path, REPO_ROOT)


def test_load_candidate_rejects_non_object(tmp_path: Path) -> None:
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(CandidateError):
        load_candidate(path, REPO_ROOT)


def test_build_evidence_bundle_is_content_addressed() -> None:
    bundle = build_evidence_bundle(
        artifact_id="EB-0001",
        created_at=NOW,
        actor=ACTOR,
        run_id=RUN_ID,
        candidate=_candidate(),
    )
    assert bundle["artifact_type"] == "evidence-bundle"
    assert validate_artifact(bundle, REPO_ROOT) == []
    kinds = [item["kind"] for item in bundle["items"]]
    assert kinds.count("signature") == 1
    assert kinds.count("policy-decision") == 2
    assert kinds.count("approval") == 1
    assert bundle["bundle_digest"] == bundle_digest(
        bundle["image"], bundle["candidate_digest"], bundle["items"]
    )


def test_bundle_digest_changes_with_evidence() -> None:
    candidate = _candidate()
    first = build_evidence_bundle(
        artifact_id="EB-0001", created_at=NOW, actor=ACTOR, run_id=RUN_ID, candidate=candidate
    )
    tampered = json.loads(json.dumps(candidate))
    tampered["sbom"]["digest"] = "b" * 64
    second = build_evidence_bundle(
        artifact_id="EB-0001", created_at=NOW, actor=ACTOR, run_id=RUN_ID, candidate=tampered
    )
    assert first["bundle_digest"] != second["bundle_digest"]


def test_verify_release_allow_builds_valid_documents() -> None:
    with _opa_stub(_allow_body()) as (url, paths):
        verification = _verify(url)
    assert paths == ["/v1/data/sdlc/pre_deployment/decision"]
    assert verification.allow is True
    assert verification.decision["point"] == "pre-deployment"
    assert verification.decision["decision"] == "allow"
    assert validate_artifact(verification.decision, REPO_ROOT) == []
    assert verification.bundle["policy_decision_ref"] == "PD-0001"
    assert validate_artifact(verification.bundle, REPO_ROOT) == []


def test_verify_release_deny_reports_reason_codes() -> None:
    with _opa_stub(_deny_body()) as (url, _):
        verification = _verify(url)
    assert verification.allow is False
    assert verification.reason_codes == ("MISSING_SBOM",)
    assert verification.decision["decision"] == "deny"


def test_verify_release_fails_closed_when_policy_unavailable() -> None:
    verification = verify_release(
        PolicyClient(base_url="http://127.0.0.1:1", timeout=0.5),
        _candidate(),
        bundle_id="EB-0001",
        decision_id="PD-0001",
        created_at=NOW,
        actor=ACTOR,
        run_id=RUN_ID,
        repo_root=REPO_ROOT,
    )
    assert verification.allow is False
    assert "POLICY_UNAVAILABLE" in verification.reason_codes


def test_cli_deploy_verify_allow_writes_artifacts(tmp_path: Path) -> None:
    output = tmp_path / "evidence"
    with _opa_stub(_allow_body()) as (url, _):
        code = main(
            [
                "deploy-verify",
                str(EXAMPLE),
                "--opa-url",
                url,
                "--run-id",
                "RUN-cli-deploy-verify",
                "--now",
                NOW,
                "--output-dir",
                str(output),
            ]
        )
    assert code == 0
    bundle = json.loads((output / "evidence-bundle.json").read_text(encoding="utf-8"))
    decision = json.loads((output / "policy-decision.json").read_text(encoding="utf-8"))
    assert validate_artifact(bundle, REPO_ROOT) == []
    assert validate_artifact(decision, REPO_ROOT) == []


def test_cli_deploy_verify_deny_exits_nonzero(tmp_path: Path) -> None:
    with _opa_stub(_deny_body()) as (url, _):
        code = main(
            [
                "deploy-verify",
                str(EXAMPLE),
                "--opa-url",
                url,
                "--now",
                NOW,
                "--output-dir",
                str(tmp_path),
            ]
        )
    assert code == 1
    decision = json.loads((tmp_path / "policy-decision.json").read_text(encoding="utf-8"))
    assert decision["decision"] == "deny"


def test_cli_deploy_verify_rejects_invalid_candidate(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"artifact_type": "release-candidate"}), encoding="utf-8")
    assert main(["deploy-verify", str(path)]) == 1
