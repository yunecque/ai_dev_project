"""MCP server exposing allowlisted tools under capability auth (M6, TASK-0004).

The server is the single door for the external agent (ADR-0011/0014): it speaks a minimal
JSON-RPC 2.0 MCP surface (``initialize``, ``tools/list``, ``tools/call``) and delegates every
execution to the policy- and capability-gated :class:`RunnerExecutor`. Failures are fail-closed:
a missing capability is rejected before any execution, and denials are reported as tool errors.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from ..runner.executor import RunnerExecutor
from ..tools import ToolRegistry
from . import protocol

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "secure-agentic-sdlc"
SERVER_VERSION = "0.1.0"

REASON_AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"

_AUTH_FIELDS = ("run_id", "token", "scope")


class MCPServer:
    """In-process MCP server. Transport (stdio/HTTP) is intentionally out of scope here."""

    def __init__(self, *, executor: RunnerExecutor, tools: ToolRegistry) -> None:
        self._executor = executor
        self._tools = tools
        self._decision_seq = 0
        self._evidence_seq = 0

    def handle(self, message: Mapping[str, Any]) -> dict[str, Any]:
        request_id = message.get("id")
        if message.get("jsonrpc") != protocol.JSONRPC_VERSION:
            return protocol.error(request_id, protocol.INVALID_REQUEST, "jsonrpc must be 2.0")
        method = message.get("method")
        if not isinstance(method, str):
            return protocol.error(request_id, protocol.INVALID_REQUEST, "missing method")
        params = message.get("params")
        params = params if isinstance(params, Mapping) else {}

        if method == "initialize":
            return protocol.result(request_id, self._initialize())
        if method in {"notifications/initialized", "ping"}:
            return protocol.result(request_id, {})
        if method == "tools/list":
            return protocol.result(request_id, self._list_tools())
        if method == "tools/call":
            return self._call(request_id, params)
        return protocol.error(request_id, protocol.METHOD_NOT_FOUND, f"unknown method {method!r}")

    def handle_line(self, line: str) -> str:
        """Parse and dispatch a single JSON-RPC line, returning a JSON line response."""
        message = protocol.parse_line(line)
        if message is None:
            return json.dumps(protocol.error(None, protocol.PARSE_ERROR, "invalid JSON"))
        return json.dumps(self.handle(message), ensure_ascii=False)

    def _initialize(self) -> dict[str, Any]:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "capabilities": {"tools": {}},
        }

    def _list_tools(self) -> dict[str, Any]:
        tools: list[dict[str, Any]] = []
        for name in self._tools.names():
            spec = self._tools.get(name)
            tools.append(
                {
                    "name": spec.name,
                    "description": spec.description,
                    "inputSchema": dict(spec.args_schema),
                }
            )
        return {"tools": tools}

    def _call(self, request_id: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        if not isinstance(name, str) or not name:
            return protocol.error(request_id, protocol.INVALID_PARAMS, "missing tool name")
        arguments = params.get("arguments", {})
        if not isinstance(arguments, Mapping):
            return protocol.error(request_id, protocol.INVALID_PARAMS, "arguments must be an object")
        auth: dict[str, str] = {}
        for field in _AUTH_FIELDS:
            value = params.get(field)
            if not isinstance(value, str) or not value:
                return protocol.error(
                    request_id, protocol.INVALID_PARAMS, f"missing capability field {field!r}"
                )
            auth[field] = value

        result = self._executor.execute(
            run_id=auth["run_id"],
            token=auth["token"],
            tool=name,
            args=arguments,
            scope=auth["scope"],
            created_at=self._now(),
            decision_id=self._next_decision_id(),
            evidence_id=self._next_evidence_id(),
        )
        if not result.allowed:
            return protocol.result(
                request_id,
                {
                    "content": [{"type": "text", "text": result.reason}],
                    "isError": True,
                    "structuredContent": {"reason": result.reason},
                },
            )
        payload = dict(result.output or {})
        return protocol.result(
            request_id,
            {
                "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
                "isError": False,
                "structuredContent": payload,
            },
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _next_decision_id(self) -> str:
        self._decision_seq += 1
        return f"PD-{self._decision_seq:04d}"

    def _next_evidence_id(self) -> str:
        self._evidence_seq += 1
        return f"EV-{self._evidence_seq:04d}"