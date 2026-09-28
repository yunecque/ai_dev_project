"""Tests for the allowlisted tool registry (M6, TASK-0001)."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from sdlc.tools import (
    ArtifactStore,
    ToolRegistry,
    UnknownToolError,
    make_tool,
    register_file_tools,
    validate_instance,
)


def _handler(args: Mapping[str, Any]) -> Mapping[str, Any]:
    return {"ok": True}


def test_register_and_get_roundtrip() -> None:
    registry = ToolRegistry()
    registry.register(make_tool(name="read_artifact", scope="workspace", description="read", handler=_handler))
    spec = registry.get("read_artifact")
    assert spec.scope == "workspace"
    assert registry.names() == ("read_artifact",)
    assert "read_artifact" in registry


def test_unknown_tool_raises() -> None:
    with pytest.raises(UnknownToolError):
        ToolRegistry().get("ghost")


def test_duplicate_registration_rejected() -> None:
    registry = ToolRegistry()
    registry.register(make_tool(name="x", scope="s", description="d", handler=_handler))
    with pytest.raises(ValueError):
        registry.register(make_tool(name="x", scope="s", description="d", handler=_handler))


def test_validate_instance_reports_errors() -> None:
    schema = {
        "type": "object",
        "required": ["path"],
        "properties": {"path": {"type": "string"}},
    }
    assert validate_instance({"path": "a"}, schema) == []
    assert validate_instance({}, schema) != []
    assert validate_instance({"path": 5}, schema) != []


def _file_registry(root: Path) -> ToolRegistry:
    registry = ToolRegistry()
    register_file_tools(registry, root)
    return registry


def test_write_file_writes_inside_root(tmp_path: Path) -> None:
    spec = _file_registry(tmp_path).get("write_file")
    result = spec.handler({"path": "apps/gateway/server.go", "content": "package main"})
    assert result["path"] == "apps/gateway/server.go"
    assert result["bytes"] == len("package main")
    assert result["digest"]
    assert (tmp_path / "apps" / "gateway" / "server.go").read_text(encoding="utf-8") == "package main"


def test_write_file_rejects_parent_escape(tmp_path: Path) -> None:
    spec = _file_registry(tmp_path).get("write_file")
    with pytest.raises(ValueError):
        spec.handler({"path": "../escape.txt", "content": "x"})
    assert not (tmp_path.parent / "escape.txt").exists()


def test_write_file_rejects_absolute_path(tmp_path: Path) -> None:
    spec = _file_registry(tmp_path).get("write_file")
    with pytest.raises(ValueError):
        spec.handler({"path": "/etc/passwd", "content": "x"})


def test_write_file_rejects_empty_path(tmp_path: Path) -> None:
    spec = _file_registry(tmp_path).get("write_file")
    with pytest.raises(ValueError):
        spec.handler({"path": "", "content": "x"})


def test_artifact_store_reads_missing_as_keyerror(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path)
    assert store.list_ids() == []
    with pytest.raises(KeyError):
        store.read("missing")