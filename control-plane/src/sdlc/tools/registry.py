"""Allowlisted tool registry for the agent execution layer (M6, ADR-0014).

Tools are declared with an explicit ``scope`` and JSON schemas for their arguments and result.
There is no arbitrary shell: only registered tools can be executed, and the runner fails closed on
unknown tools and schema violations.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator

ToolHandler = Callable[[Mapping[str, Any]], Mapping[str, Any]]


class UnknownToolError(KeyError):
    """Raised when a tool name is not present in the registry."""


def validate_instance(instance: Any, schema: Mapping[str, Any]) -> list[str]:
    """Return human-readable validation errors for ``instance`` against an inline schema."""
    validator = Draft202012Validator(dict(schema))
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errors]


@dataclass(frozen=True)
class ToolSpec:
    """Declarative contract for a single allowlisted tool."""

    name: str
    scope: str
    description: str
    args_schema: Mapping[str, Any]
    result_schema: Mapping[str, Any]
    handler: ToolHandler


class ToolRegistry:
    """Registry of allowlisted tools; lookups fail closed on unknown names."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if not spec.name:
            raise ValueError("tool name must be non-empty")
        if spec.name in self._tools:
            raise ValueError(f"tool already registered: {spec.name}")
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise UnknownToolError(name) from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def __contains__(self, name: object) -> bool:
        return name in self._tools


def make_tool(
    *,
    name: str,
    scope: str,
    description: str,
    handler: ToolHandler,
    args_schema: Mapping[str, Any] | None = None,
    result_schema: Mapping[str, Any] | None = None,
) -> ToolSpec:
    """Convenience constructor with permissive default schemas (object with no constraints)."""
    default: Mapping[str, Any] = {"type": "object"}
    return ToolSpec(
        name=name,
        scope=scope,
        description=description,
        args_schema=args_schema or default,
        result_schema=result_schema or default,
        handler=handler,
    )