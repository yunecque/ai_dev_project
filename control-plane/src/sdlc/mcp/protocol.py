"""Minimal JSON-RPC 2.0 helpers for the MCP bridge (M6, TASK-0004)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

JSONRPC_VERSION = "2.0"

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


def request(request_id: Any, method: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    message: dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "id": request_id, "method": method}
    if params is not None:
        message["params"] = dict(params)
    return message


def result(request_id: Any, payload: Mapping[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": JSONRPC_VERSION, "id": request_id, "result": dict(payload)}


def error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def parse_line(line: str) -> dict[str, Any] | None:
    """Parse a JSON-RPC line; return None on failure."""
    try:
        message: Any = json.loads(line)
    except json.JSONDecodeError:
        return None
    if not isinstance(message, dict):
        return None
    return message