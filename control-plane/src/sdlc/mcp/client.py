"""In-process MCP client for tests and embedding (M6, TASK-0004)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .protocol import request


class MCPError(RuntimeError):
    """Raised when the server returns a JSON-RPC error."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


class InProcessClient:
    """Drive an :class:`~sdlc.mcp.server.MCPServer` without a transport."""

    def __init__(self, server: Any) -> None:
        self._server = server
        self._counter = 0

    def _next_id(self) -> int:
        self._counter += 1
        return self._counter

    def _request(self, method: str, params: Mapping[str, Any] | None = None) -> Mapping[str, Any]:
        request_id = self._next_id()
        response = self._server.handle(request(request_id, method, params))
        if "error" in response:
            error = response["error"]
            raise MCPError(int(error["code"]), str(error["message"]))
        result: Mapping[str, Any] = response["result"]
        return result

    def initialize(self) -> Mapping[str, Any]:
        return self._request("initialize")

    def list_tools(self) -> Mapping[str, Any]:
        return self._request("tools/list")

    def call_tool(
        self,
        name: str,
        arguments: Mapping[str, Any],
        *,
        run_id: str,
        token: str,
        scope: str,
    ) -> Mapping[str, Any]:
        return self._request(
            "tools/call",
            {
                "name": name,
                "arguments": dict(arguments),
                "run_id": run_id,
                "token": token,
                "scope": scope,
            },
        )