"""Guard tests for the mini PC staging deployment artifacts (M4, TASK-0005; ADR-0005/0010).

Validates the staging compose, the systemd unit, and the env template: app images come from a
pinned GHCR registry/tag, long-running services restart, migrations gate the services, configs are
reused from infra/compose, and no secrets are committed.
"""

from __future__ import annotations

from typing import Any

import yaml

from sdlc.artifacts import find_repo_root

REPO_ROOT = find_repo_root()
STAGING = REPO_ROOT / "infra" / "staging"
COMPOSE_PATH = STAGING / "docker-compose.yml"

REQUIRED_SERVICES = {
    "postgres", "nats", "keycloak", "opa", "otel-collector", "prometheus", "grafana",
    "loki", "tempo", "migrate", "domain", "publisher", "worker", "gateway",
}
APP_SERVICES = {"domain", "publisher", "worker", "gateway"}


def _compose() -> dict[str, Any]:
    return yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))


def test_required_services_present() -> None:
    services = _compose()["services"]
    assert REQUIRED_SERVICES <= set(services), REQUIRED_SERVICES - set(services)


def test_app_images_are_pinned_from_ghcr() -> None:
    services = _compose()["services"]
    for name in APP_SERVICES:
        image = services[name]["image"]
        assert "${IMAGE_REGISTRY" in image, image
        assert "${IMAGE_TAG" in image, image
        assert not image.endswith(":latest"), image


def test_long_running_services_restart_and_migrate_does_not() -> None:
    services = _compose()["services"]
    for name, service in services.items():
        if name == "migrate":
            assert service["restart"] == "no"
            continue
        assert service["restart"] == "unless-stopped", name


def test_migrations_gate_the_app_services() -> None:
    services = _compose()["services"]
    migrate = services["migrate"]
    assert migrate["depends_on"]["postgres"]["condition"] == "service_healthy"
    mounts = " ".join(migrate["volumes"])
    assert "/migrations/domain" in mounts and "/migrations/worker" in mounts
    for name in ("domain", "publisher", "worker"):
        dependency = services[name]["depends_on"]["migrate"]
        assert dependency["condition"] == "service_completed_successfully", name


def test_app_services_export_telemetry() -> None:
    services = _compose()["services"]
    for name in APP_SERVICES:
        environment = services[name]["environment"]
        assert environment["OTEL_EXPORTER_OTLP_ENDPOINT"] == "http://otel-collector:4317", name


def test_configs_reused_and_no_local_volume_binds() -> None:
    services = _compose()["services"]
    all_mounts = [mount for service in services.values() for mount in service.get("volumes", [])]
    assert any("../compose/otel-collector.yaml" in mount for mount in all_mounts)
    assert not any("./volumes" in mount for mount in all_mounts), all_mounts
    assert "postgres-data" in _compose()["volumes"]


def test_systemd_unit_runs_docker_compose() -> None:
    unit = (STAGING / "systemd" / "secure-agentic-sdlc.service").read_text(encoding="utf-8")
    assert "[Unit]" in unit and "[Service]" in unit and "[Install]" in unit
    assert "WorkingDirectory=/opt/secure-agentic-sdlc/infra/staging" in unit
    assert "/usr/bin/docker compose" in unit


def test_env_template_has_no_real_secrets() -> None:
    template = (STAGING / ".env.example").read_text(encoding="utf-8")
    assert "CHANGE_ME" in template
    for line in template.splitlines():
        if line.startswith(("POSTGRES_PASSWORD=", "GRAFANA_ADMIN_PASSWORD=")):
            assert line.endswith("CHANGE_ME"), line
    assert not (STAGING / ".env").exists(), "staging .env must not be committed"


def test_deploy_script_uses_env_file() -> None:
    script = (STAGING / "deploy.sh").read_text(encoding="utf-8")
    assert "docker compose" in script
    assert "ENV_FILE" in script
