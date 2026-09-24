"""Guard tests for golden-path SLO alert rules (M4, TASK-0004; ADR-0010).

Validates that Prometheus loads the rule files, that the compose stack mounts them, and that
every alert is well-formed (query, duration, severity, summary/description) with the required
golden-path alerts present.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from sdlc.artifacts import find_repo_root

REPO_ROOT = find_repo_root()
COMPOSE = REPO_ROOT / "infra" / "compose"
RULES_DIR = COMPOSE / "prometheus" / "rules"

REQUIRED_ALERTS = {
    "GoldenPathServiceDown": "critical",
    "GoldenPathHighErrorRate": "warning",
    "GoldenPathHighLatency": "warning",
}
SEVERITIES = {"critical", "warning", "info"}


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _all_rules() -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for path in sorted(RULES_DIR.glob("*.yml")):
        for group in _load_yaml(path)["groups"]:
            rules.extend(group["rules"])
    return rules


def test_prometheus_loads_rule_files() -> None:
    config = _load_yaml(COMPOSE / "prometheus.yml")
    assert "/etc/prometheus/rules/*.yml" in config["rule_files"]


def test_compose_mounts_rule_files() -> None:
    services = _load_yaml(COMPOSE / "docker-compose.yml")["services"]
    volumes = services["prometheus"]["volumes"]
    assert any(v.startswith("./prometheus/rules:") for v in volumes), volumes


def test_alerts_are_well_formed() -> None:
    rules = _all_rules()
    assert rules, "no alert rules found"
    for rule in rules:
        assert rule["alert"], rule
        assert str(rule["expr"]).strip(), rule["alert"]
        assert rule.get("for"), f"{rule['alert']} has no `for` duration"
        assert rule["labels"]["severity"] in SEVERITIES, rule["alert"]
        annotations = rule["annotations"]
        assert annotations.get("summary"), rule["alert"]
        assert annotations.get("description"), rule["alert"]


def test_required_golden_path_alerts_present() -> None:
    severities = {rule["alert"]: rule["labels"]["severity"] for rule in _all_rules()}
    for name, severity in REQUIRED_ALERTS.items():
        assert name in severities, f"missing alert {name}"
        assert severities[name] == severity, f"{name} severity is {severities[name]}"
