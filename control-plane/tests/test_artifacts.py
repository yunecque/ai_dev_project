"""Tests for artifact schema validation and rendering."""

from __future__ import annotations

import copy
import json

import pytest

from sdlc.artifacts import find_repo_root, render_artifact, validate_artifact, validate_file

REPO_ROOT = find_repo_root()
EXAMPLES = REPO_ROOT / "specs" / "examples"


def _load(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "name",
    [
        "idea.json",
        "specification.json",
        "threat-model.json",
        "plan.json",
        "task.json",
        "review.json",
        "security-review.json",
        "policy-decision.json",
        "evidence-record.json",
        "waiver.json",
    ],
)
def test_examples_are_valid(name: str) -> None:
    assert validate_artifact(_load(name), REPO_ROOT) == []


def test_invalid_severity_is_rejected() -> None:
    threat_model = _load("threat-model.json")
    broken = copy.deepcopy(threat_model)
    broken["risks"][0]["severity"] = "catastrophic"
    errors = validate_artifact(broken, REPO_ROOT)
    assert errors, "expected validation error for an unknown severity"


def test_critical_waiver_is_rejected_by_schema() -> None:
    waiver = _load("waiver.json")
    broken = copy.deepcopy(waiver)
    broken["severity"] = "critical"
    assert validate_artifact(broken, REPO_ROOT), "waivers must be medium-only"


@pytest.mark.parametrize(
    "name",
    ["idea.json", "specification.json", "threat-model.json", "plan.json", "task.json", "policy-decision.json", "evidence-record.json"],
)
def test_render_produces_markdown(name: str) -> None:
    markdown = render_artifact(_load(name), source=name)
    assert markdown.startswith("<!-- GENERATED FILE.")
    assert "#" in markdown


def test_repo_baseline_is_valid() -> None:
    assert validate_file(REPO_ROOT / "baseline.json", REPO_ROOT) == []


def test_baseline_renders() -> None:
    baseline = json.loads((REPO_ROOT / "baseline.json").read_text(encoding="utf-8"))
    markdown = render_artifact(baseline, source="baseline.json")
    assert "BASELINE-V1" in markdown
    assert "strict" in markdown
