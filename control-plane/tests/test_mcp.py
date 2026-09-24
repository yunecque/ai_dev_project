"""Tests for the in-process MCP bridge (M6, TASK-0004).

Every call is capability-authenticated and policy-gated; missing auth, unknown methods, and
policy/tool failures are all fail-closed.
"""

from __future__ import annotations

import json
import socket
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from sdlc.evidence import EvidenceStore
from sdlc.mcp import INVALID_PARAMS, METHOD_NOT_FOUND, InProcessClient, MCPError, MCPServer
from sdlc.policy import REASON_ALLOWED, REASON_POLICY_UNAVAILABLE, PolicyClient
from sdlc.runner import REASON_UNKNOWN_TOOL, RunnerExecutor, RunRegistry
from sdlc.tools import ToolRegistry, make_tool

SECRET = b"mcp-secret"
ACTOR = {"type": "agent", "id": "implementer", "role": "implementer"}

ARGS_SCHEMA = {
    "type": "object",
    "required": ["path"],
    "properties": {"path": {"type": "string"}},
}


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def _opa_stub(allow: bool) -> Iterator[str]:
    body = json.dumps(
        {"result": {"allow": allow, "reason_codes": [REASON_ALLOWED if allow else "DENIED"]}}
    ).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _tools() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        make_tool(
            name="read_artifact",
            scope="workspace",
            description="read an artifact",
            handler=lambda args: {"content": "hello"},
            args_schema=ARGS_SCHEMA,
        )
    )
    return registry


def _server(policy: Any, capabilities: RunRegistry, tmp_path: Path) -> MCPServer:
    executor = RunnerExecutor(
        policy=policy,
        capabilities=capabilities,
        tools=_tools(),
        evidence_store=EvidenceStore(tmp_path),
    )
    return MCPServer(executor=executor, tools=_tools())


def _run(capabilities: RunRegistry) -> str:
    run = capabilities.start(ACTOR)
    return run.run_id


def test_initialize_and_list_tools(tmp_path: Path) -> None:
    capabilities = RunRegistry(secret=SECRET)
    with _opa_stub(allow=True) as url:
        client = InProcessClient(_server(PolicyClient(base_url=url), capabilities, tmp_path))
    init = client.initialize()
    assert init["protocolVersion"]
    assert "tools" in init["capabilities"]
    tools = client.list_tools()["tools"]
    assert tools[0]["name"] == "read_artifact"
    assert tools[0]["inputSchema"] == ARGS_SCHEMA


def test_call_tool_allowed(tmp_path: Path) -> None:
    capabilities = RunRegistry(secret=SECRET)
    run_id = _run(capabilities)
    token = capabilities.issue(run_id, tool="read_artifact", scope="workspace")
    with _opa_stub(allow=True) as url:
        client = InProcessClient(_server(PolicyClient(base_url=url), capabilities, tmp_path))
        response = client.call_tool(
            "read_artifact", {"path": "specs/examples/idea.json"}, run_id=run_id, token=token, scope="workspace"
        )
    assert response["isError"] is False
    assert response["structuredContent"] == {"content": "hello"}


def test_call_tool_requires_capability(tmp_path: Path) -> None:
    capabilities = RunRegistry(secret=SECRET)
    run_id = _run(capabilities)
    with _opa_stub(allow=True) as url:
        client = InProcessClient(_server(PolicyClient(base_url=url), capabilities, tmp_path))
        with pytest.raises(MCPError) as excinfo:
            client.call_tool("read_artifact", {"path": "a"}, run_id=run_id, token="", scope="workspace")
    assert excinfo.value.code == INVALID_PARAMS


def test_policy_unavailable_is_tool_error(tmp_path: Path) -> None:
    capabilities = RunRegistry(secret=SECRET)
    run_id = _run(capabilities)
    token = capabilities.issue(run_id, tool="read_artifact", scope="workspace")
    policy = PolicyClient(base_url=f"http://127.0.0.1:{_free_port()}", timeout=0.5)
    client = InProcessClient(_server(policy, capabilities, tmp_path))
    response = client.call_tool(
        "read_artifact", {"path": "a"}, run_id=run_id, token=token, scope="workspace"
    )
    assert response["isError"] is True
    assert response["structuredContent"]["reason"] == REASON_POLICY_UNAVAILABLE


def test_unknown_tool_is_tool_error(tmp_path: Path) -> None:
    capabilities = RunRegistry(secret=SECRET)
    run_id = _run(capabilities)
    token = capabilities.issue(run_id, tool="ghost", scope="workspace")
    with _opa_stub(allow=True) as url:
        client = InProcessClient(_server(PolicyClient(base_url=url), capabilities, tmp_path))
        response = client.call_tool(
            "ghost", {}, run_id=run_id, token=token, scope="workspace"
        )
    assert response["isError"] is True
    assert response["structuredContent"]["reason"] == REASON_UNKNOWN_TOOL


def test_unknown_method_is_rpc_error(tmp_path: Path) -> None:
    capabilities = RunRegistry(secret=SECRET)
    with _opa_stub(allow=True) as url:
        client = InProcessClient(_server(PolicyClient(base_url=url), capabilities, tmp_path))
        with pytest.raises(MCPError) as excinfo:
            client._request("tools/explode")
    assert excinfo.value.code == METHOD_NOT_FOUND


def test_malformed_line_is_parse_error(tmp_path: Path) -> None:
    capabilities = RunRegistry(secret=SECRET)
    with _opa_stub(allow=True) as url:
        server = _server(PolicyClient(base_url=url), capabilities, tmp_path)
    raw = server.handle_line("not json")
    decoded = json.loads(raw)
    assert decoded["error"]["code"] == -32700