"""MCP bridge: capability-authenticated JSON-RPC surface over the runner executor (M6, TASK-0004)."""

from __future__ import annotations

from .client import InProcessClient, MCPError
from .protocol import (
    INVALID_PARAMS,
    INVALID_REQUEST,
    JSONRPC_VERSION,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    error,
    parse_line,
    request,
    result,
)
from .server import PROTOCOL_VERSION, SERVER_NAME, SERVER_VERSION, MCPServer

__all__ = [
    "INVALID_PARAMS",
    "INVALID_REQUEST",
    "JSONRPC_VERSION",
    "METHOD_NOT_FOUND",
    "PARSE_ERROR",
    "PROTOCOL_VERSION",
    "SERVER_NAME",
    "SERVER_VERSION",
    "InProcessClient",
    "MCPError",
    "MCPServer",
    "error",
    "parse_line",
    "request",
    "result",
]