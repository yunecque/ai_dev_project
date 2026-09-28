"""Capability bootstrap for the stdio MCP bridge (M6, local single-door wiring).

The external agent (opencode) speaks plain MCP and does not carry platform capability
tokens. The bridge is trusted platform code: for each ``tools/call`` it mints a scoped,
ephemeral capability token for the requested tool and injects ``run_id``/``token``/``scope``
before the request reaches the policy- and capability-gated executor.

Explicit capability fields from the caller are never overridden, so an upstream
orchestrator that already holds a token keeps full control. Unknown tools are passed
through untouched — the executor rejects them fail-closed.
"""

from __future__ import annotations

import json

from ..runner.registry import RunRegistry
from ..tools import ToolRegistry, UnknownToolError

CAPABILITY_FIELDS = ("run_id", "token", "scope")


def inject_capability(
    line: str,
    *,
    capabilities: RunRegistry,
    tools: ToolRegistry,
    run_id: str,
) -> str:
    """Return ``line`` with capability fields injected for a ``tools/call`` request."""
    try:
        message = json.loads(line)
    except json.JSONDecodeError:
        return line
    if not isinstance(message, dict) or message.get("method") != "tools/call":
        return line
    params = message.get("params")
    if not isinstance(params, dict):
        return line
    if all(isinstance(params.get(field), str) and params[field] for field in CAPABILITY_FIELDS):
        return line
    name = params.get("name")
    if not isinstance(name, str):
        return line
    try:
        spec = tools.get(name)
    except UnknownToolError:
        return line
    params.setdefault("run_id", run_id)
    params.setdefault("scope", spec.scope)
    params.setdefault("token", capabilities.issue(run_id, tool=name, scope=spec.scope))
    return json.dumps(message)


__all__ = ["CAPABILITY_FIELDS", "inject_capability"]
