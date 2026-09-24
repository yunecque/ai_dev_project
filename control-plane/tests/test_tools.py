"""Tests for the allowlisted tool registry (M6, TASK-0001)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from sdlc.tools import ToolRegistry, UnknownToolError, make_tool, validate_instance


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