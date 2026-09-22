"""Tests for the evidence store, compression layer, and evidence records (M1, TASK-0004)."""

from __future__ import annotations

from pathlib import Path

import pytest

from sdlc.artifacts import find_repo_root, validate_artifact
from sdlc.evidence import (
    DEFAULT_MAX_BYTES,
    EvidenceStore,
    SensitiveContentError,
    build_evidence_record,
    compress_for_context,
    process_tool_output,
)
from sdlc.trust import TrustTier

REPO_ROOT = find_repo_root()
ACTOR = {"type": "agent", "id": "implementer", "role": "implementer"}
RUN_ID = "RUN-implementer-0001"
CREATED_AT = "2026-09-22T00:00:00Z"


def _large_text() -> str:
    return "line of tool output\n" * (DEFAULT_MAX_BYTES)


def test_small_untrusted_output_is_not_compressed() -> None:
    result = compress_for_context("short output", tier=TrustTier.UNTRUSTED)
    assert result.applied is False
    assert result.context_text == "short output"
    assert len(result.original_digest) == 64


def test_large_untrusted_output_is_compressed() -> None:
    text = _large_text()
    result = compress_for_context(text, tier=TrustTier.UNTRUSTED)
    assert result.applied is True
    assert len(result.context_text.encode("utf-8")) < len(text.encode("utf-8"))
    assert result.recovery_handle == f"sha256:{result.original_digest}"
    assert result.compressed_size_bytes < result.original_size_bytes


def test_trusted_output_is_never_compressed() -> None:
    result = compress_for_context(_large_text(), tier=TrustTier.TRUSTED)
    assert result.applied is False


def test_store_is_content_addressed_and_roundtrips(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path)
    data = b"byte-exact payload"
    digest = store.put(data)
    assert len(digest) == 64
    assert store.get(digest) == data
    assert store.resolve(f"sha256:{digest}") == data


def test_store_rejects_unknown_digest(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path)
    with pytest.raises(KeyError):
        store.get("0" * 64)


def test_process_tool_output_produces_valid_record(tmp_path: Path) -> None:
    text = _large_text()
    store = EvidenceStore(tmp_path)
    outcome = process_tool_output(
        text,
        action="tool.bash.output",
        actor=ACTOR,
        run_id=RUN_ID,
        artifact_id="EV-0001",
        created_at=CREATED_AT,
        store=store,
    )
    assert validate_artifact(outcome.record, REPO_ROOT) == []
    compression = outcome.record["compression"]
    assert compression["applied"] is True
    assert store.resolve(compression["recovery_handle"]) == text.encode("utf-8")
    assert outcome.record["artifact_digest"] == outcome.digest
    assert outcome.context_text != text


def test_small_output_record_is_valid(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path)
    outcome = process_tool_output(
        "small",
        action="tool.bash.output",
        actor=ACTOR,
        run_id=RUN_ID,
        artifact_id="EV-0002",
        created_at=CREATED_AT,
        store=store,
    )
    assert validate_artifact(outcome.record, REPO_ROOT) == []
    assert outcome.record["compression"]["applied"] is False


def test_sensitive_content_must_not_enter_context(tmp_path: Path) -> None:
    store = EvidenceStore(tmp_path)
    with pytest.raises(SensitiveContentError):
        process_tool_output(
            "password=hunter2",
            action="tool.bash.output",
            actor=ACTOR,
            run_id=RUN_ID,
            artifact_id="EV-0003",
            created_at=CREATED_AT,
            store=store,
            tier=TrustTier.SENSITIVE,
        )


def test_build_evidence_record_validates(tmp_path: Path) -> None:
    result = compress_for_context("data", tier=TrustTier.UNTRUSTED)
    record = build_evidence_record(
        artifact_id="EV-0004",
        created_at=CREATED_AT,
        actor=ACTOR,
        run_id=RUN_ID,
        action="artifact.transition",
        trust_tier=TrustTier.UNTRUSTED,
        sensitivity="none",
        artifact_digest=result.original_digest,
        artifact_ref="specs/examples/plan.json",
        policy_decision_ref="specs/examples/policy-decision.json",
        compression=result,
    )
    assert validate_artifact(record, REPO_ROOT) == []