"""Tests for the `.opencode/` agent-restriction config (M6, TASK-0005, protected zone)."""

from __future__ import annotations

import json

import yaml

from sdlc.artifacts import find_repo_root

REPO_ROOT = find_repo_root()
OPENCODE = REPO_ROOT / ".opencode"
ROLES = ("grill", "grill-security", "planner", "task-writer", "implementer", "reviewer")


def _config() -> dict:
    return json.loads((OPENCODE / "opencode.json").read_text(encoding="utf-8"))


def test_schema_and_instructions_declared() -> None:
    config = _config()
    assert config["$schema"] == "https://opencode.ai/config.json"
    assert "AGENTS.md" in config["instructions"]


def test_mcp_server_registered_as_local_stdio() -> None:
    server = _config()["mcp"]["sdlc-platform"]
    assert server["type"] == "local"
    assert server["enabled"] is True
    assert server["command"] == ["sdlc", "mcp"]
    assert server["environment"]["OPA_URL"].startswith("http")


def test_permission_locks_down_direct_access() -> None:
    permission = _config()["permission"]
    assert permission["edit"] == "deny"
    assert permission["bash"] == "deny"
    assert permission["webfetch"] == "deny"
    assert permission["websearch"] == "deny"
    assert permission["external_directory"] == {"*": "deny"}
    read = permission["read"]
    assert read["*"] == "allow"
    assert read[".env"] == "deny"
    assert read["secrets/**"] == "deny"
    assert read["**/*.key"] == "deny"


def test_opa_guard_plugin_registered_and_gates_tools() -> None:
    assert "./plugin/opa-guard.ts" in _config()["plugin"]
    plugin = (OPENCODE / "plugin" / "opa-guard.ts").read_text(encoding="utf-8")
    assert "tool.execute.before" in plugin
    assert "permission.ask" in plugin
    assert "/v1/data/sdlc/pre_tool_call/decision" in plugin
    assert "POLICY_UNAVAILABLE" in plugin


def test_role_profiles_exist_and_restrict_permissions() -> None:
    for role in ROLES:
        path = OPENCODE / "agent" / f"{role}.md"
        assert path.is_file(), f"missing role profile {role}"
        text = path.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        frontmatter = text.split("---", 2)[1]
        metadata = yaml.safe_load(frontmatter)
        assert metadata.get("description")
        assert metadata.get("mode") == "primary"
        assert metadata["permission"]["edit"] == "deny"
        assert metadata["permission"]["bash"] == "deny"


def test_config_contains_no_secrets() -> None:
    raw = (OPENCODE / "opencode.json").read_text(encoding="utf-8").lower()
    for marker in ("password", "api_key", "apikey", "private key", "bearer "):
        assert marker not in raw, f"unexpected sensitive marker {marker!r} in opencode.json"
    assert "SDLC_MCP_SECRET" not in (OPENCODE / "opencode.json").read_text(encoding="utf-8")