"""Traceability chain audit (M5): idea -> ... -> review over canonical artifacts.

The chain is derived from the ``links`` graph of the canonical JSON artifacts. These tests cover
the happy path (the golden-path feature examples form a complete chain), gap detection, and the
``sdlc trace`` CLI.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sdlc.artifacts import find_repo_root
from sdlc.cli import main
from sdlc.traceability import CHAIN_ORDER, format_report, trace_feature

REPO_ROOT = find_repo_root()


def _doc(artifact_type: str, artifact_id: str, *, feature_id: str | None = None,
         links: list[dict[str, str]] | None = None) -> dict[str, Any]:
    doc: dict[str, Any] = {"artifact_type": artifact_type, "id": artifact_id}
    if feature_id is not None:
        doc["feature_id"] = feature_id
    if links is not None:
        doc["links"] = links
    return doc


def test_golden_path_feature_chain_is_complete() -> None:
    report = trace_feature(REPO_ROOT, "FEAT-0001")
    assert report.complete, format_report(report)
    assert report.ordered_types == CHAIN_ORDER
    ids = {node.artifact_id for node in report.nodes}
    assert {"IDEA-0001", "SPEC-0001", "TM-0001", "PLAN-0001", "TASK-0001", "REV-0001", "SECREV-0001"} <= ids
    assert not report.dangling


def test_missing_lifecycle_stage_is_reported() -> None:
    artifacts = {
        (REPO_ROOT / "specs/examples/specification.json"): _doc(
            "specification", "SPEC-9999", feature_id="FEAT-9999"
        ),
        (REPO_ROOT / "specs/examples/idea.json"): _doc("idea", "IDEA-9999"),
    }
    report = trace_feature(REPO_ROOT, "FEAT-9999", artifacts=artifacts)
    assert not report.complete
    assert "threat-model" in report.missing_types
    assert "task" in report.missing_types


def test_dangling_local_link_is_reported() -> None:
    artifacts = {
        (REPO_ROOT / "specs/examples/specification.json"): _doc(
            "specification",
            "SPEC-9999",
            feature_id="FEAT-9999",
            links=[{"rel": "requirement", "href": "specs/examples/does-not-exist.json"}],
        ),
    }
    report = trace_feature(REPO_ROOT, "FEAT-9999", artifacts=artifacts)
    assert "specs/examples/does-not-exist.json" in report.dangling
    assert not report.complete


def test_trace_cli_reports_complete_chain(capsys: Any) -> None:
    exit_code = main(["trace", "--feature", "FEAT-0001", "--repo-root", str(REPO_ROOT)])
    assert exit_code == 0
    assert "COMPLETE" in capsys.readouterr().out


def test_trace_cli_json_output(capsys: Any) -> None:
    exit_code = main(
        ["trace", "--feature", "FEAT-0001", "--repo-root", str(REPO_ROOT), "--json"]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["feature_id"] == "FEAT-0001"
    assert payload["missing_types"] == []
    assert Path("specs/examples/task.json") in {Path(node["path"]) for node in payload["nodes"]}
