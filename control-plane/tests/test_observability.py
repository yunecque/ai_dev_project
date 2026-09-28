"""Guard tests for Prometheus/Grafana observability provisioning (M4, TASK-0003; ADR-0010).

These validate the local observability stack configuration: Prometheus scrapes the OTel
Collector, Grafana datasources expose deterministic uids, the dashboard provider is wired, and
the golden-path dashboard references only provisioned datasources with non-empty queries.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from sdlc.artifacts import find_repo_root

REPO_ROOT = find_repo_root()
COMPOSE = REPO_ROOT / "infra" / "compose"
GRAFANA_PROVISIONING = COMPOSE / "grafana" / "provisioning"
DASHBOARDS_DIR = GRAFANA_PROVISIONING / "dashboards"


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _dashboard_uids() -> set[str]:
    datasources = _load_yaml(GRAFANA_PROVISIONING / "datasources" / "datasources.yaml")
    return {entry["uid"] for entry in datasources["datasources"]}


def test_prometheus_scrapes_otel_collector() -> None:
    config = _load_yaml(COMPOSE / "prometheus.yml")
    jobs = {job["job_name"]: job for job in config["scrape_configs"]}
    assert "otel-collector" in jobs
    targets = jobs["otel-collector"]["static_configs"][0]["targets"]
    assert "otel-collector:8889" in targets


def test_collector_prometheus_exporter_converts_resources() -> None:
    exporter = _load_yaml(COMPOSE / "otel-collector.yaml")["exporters"]["prometheus"]
    assert exporter["resource_to_telemetry_conversion"]["enabled"] is True


def test_grafana_datasources_have_deterministic_uids() -> None:
    assert _dashboard_uids() == {"prometheus", "loki", "tempo"}


def test_dashboard_provider_is_wired() -> None:
    provider = _load_yaml(DASHBOARDS_DIR / "dashboards.yaml")
    entries = provider["providers"]
    assert len(entries) == 1
    options = entries[0]["options"]
    assert entries[0]["type"] == "file"
    assert options["path"].endswith("/provisioning/dashboards")


def test_golden_path_dashboard_is_valid() -> None:
    dashboard = json.loads((DASHBOARDS_DIR / "golden-path.json").read_text(encoding="utf-8"))
    assert dashboard["title"]
    assert dashboard["schemaVersion"]
    uids = _dashboard_uids()

    panels = dashboard["panels"]
    assert panels, "dashboard has no panels"
    for panel in panels:
        assert panel["type"], panel
        assert panel["title"], panel
        assert panel["datasource"]["uid"] in uids, panel["title"]
        targets = panel["targets"]
        assert targets, panel["title"]
        for target in targets:
            assert target["expr"].strip(), panel["title"]
            assert target["datasource"]["uid"] in uids, panel["title"]
