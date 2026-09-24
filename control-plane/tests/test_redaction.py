"""Guard tests for mandatory telemetry redaction (M4, TASK-0002; ADR-0010).

The real redaction runs inside the OTel Collector (OTTL). These tests load the actual
``infra/compose/otel-collector.yaml`` and (a) assert the redaction processor is wired into every
signal pipeline, (b) assert the required secret/token/PII patterns are present, and (c) replay the
configured ``replace_pattern`` statements against sample telemetry to prove sensitive values are
removed. If a pipeline wiring or a required pattern is dropped, the guard fails.
"""

from __future__ import annotations

import json
import re
from typing import Any

import yaml

from sdlc.artifacts import find_repo_root

REPO_ROOT = find_repo_root()
CONFIG_PATH = REPO_ROOT / "infra" / "compose" / "otel-collector.yaml"
REDACT_PROCESSOR = "transform/redact"

_STATEMENT = re.compile(
    r'^replace_pattern\((?P<target>.+?), "(?P<pattern>[^"]*)", "(?P<replacement>[^"]*)"\)$'
)
_ATTRIBUTE = re.compile(r'^attributes\["(?P<key>[^"]+)"\]$')


def _config() -> dict[str, Any]:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def _statements(cfg: dict[str, Any]) -> list[str]:
    processor = cfg["processors"][REDACT_PROCESSOR]
    statements: list[str] = []
    for group, blocks in processor.items():
        if not group.endswith("_statements"):
            continue
        for block in blocks:
            statements.extend(block.get("statements", []))
    return statements


def _apply(payload: dict[str, Any], statements: list[str]) -> dict[str, Any]:
    """Replay the configured replace_pattern statements against a sample payload."""
    for statement in statements:
        match = _STATEMENT.match(statement)
        assert match, f"unsupported statement: {statement}"
        pattern = match.group("pattern")
        replacement = match.group("replacement").replace("$1", r"\1")
        attribute = _ATTRIBUTE.match(match.group("target"))
        if attribute:
            key = attribute.group("key")
            if key in payload["attributes"]:
                payload["attributes"][key] = re.sub(
                    pattern, replacement, str(payload["attributes"][key])
                )
        elif match.group("target") == "body":
            payload["body"] = re.sub(pattern, replacement, payload["body"])
        else:
            raise AssertionError(f"unsupported redaction target: {match.group('target')}")
    return payload


def test_redaction_wired_into_every_pipeline() -> None:
    cfg = _config()
    pipelines = cfg["service"]["pipelines"]
    assert set(pipelines) == {"traces", "metrics", "logs"}
    for name, pipeline in pipelines.items():
        processors = pipeline["processors"]
        assert REDACT_PROCESSOR in processors, f"{name} pipeline is not redacted: {processors}"
        assert processors.index(REDACT_PROCESSOR) < processors.index("batch")


def test_redaction_covers_every_signal_context() -> None:
    processor = _config()["processors"][REDACT_PROCESSOR]
    assert processor["error_mode"] == "ignore"
    for group in ("trace_statements", "metric_statements", "log_statements"):
        assert group in processor, f"missing {group}"


def test_required_sensitive_patterns_present() -> None:
    statements = _statements(_config())
    blob = "\n".join(statements).lower()
    for required in ("authorization", "cookie", "password", "secret", "token", "api[_-]?key"):
        assert required in blob, f"redaction pattern for {required!r} is missing"
    assert any("@" in statement for statement in statements), "email/PII redaction is missing"


def test_sample_telemetry_is_redacted() -> None:
    payload: dict[str, Any] = {
        "attributes": {
            "http.request.header.authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig",
            "http.request.header.cookie": "session=super-secret",
            "http.response.header.set-cookie": "session=super-secret",
            "http.request.method": "POST",
        },
        "body": "login user=a@example.com password=hunter2 token=abc123 api_key=xyz",
    }
    redacted = _apply(payload, _statements(_config()))
    serialized = json.dumps(redacted)

    for leaked in (
        "eyJhbGciOiJIUzI1NiJ9",
        "super-secret",
        "hunter2",
        "abc123",
        "xyz",
        "a@example.com",
    ):
        assert leaked not in serialized, f"sensitive value leaked: {leaked}"
    assert "[REDACTED]" in serialized
    assert "[REDACTED_EMAIL]" in serialized
    assert redacted["attributes"]["http.request.method"] == "POST"
