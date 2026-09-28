"""Tests for the stdio MCP bridge loop (M6): the server must survive bad requests."""

from __future__ import annotations

import io
import json

from sdlc.cli import serve_stdio
from sdlc.runner import RunRegistry
from sdlc.tools import ToolRegistry

SECRET = b"stdio-secret"


class _RaisingServer:
    """Duck-typed MCPServer double that explodes on a sentinel line."""

    def __init__(self) -> None:
        self.seen: list[str] = []

    def handle_line(self, line: str) -> str:
        self.seen.append(line)
        if line == "boom":
            raise RuntimeError("boom")
        return json.dumps({"id": len(self.seen)})


def test_serve_stdio_survives_request_failure() -> None:
    server = _RaisingServer()
    out = io.StringIO()
    serve_stdio(
        server=server,  # type: ignore[arg-type]
        capabilities=RunRegistry(secret=SECRET),
        tools=ToolRegistry(),
        run_id="RUN-test",
        stdin=io.StringIO("boom\nnot json either\n"),
        stdout=out,
    )
    lines = [json.loads(line) for line in out.getvalue().splitlines()]
    assert len(lines) == 2
    assert lines[0]["error"]["code"] == -32603
    assert lines[1] == {"id": 2}
    assert server.seen == ["boom", "not json either"]


def test_serve_stdio_ignores_blank_lines() -> None:
    server = _RaisingServer()
    out = io.StringIO()
    serve_stdio(
        server=server,  # type: ignore[arg-type]
        capabilities=RunRegistry(secret=SECRET),
        tools=ToolRegistry(),
        run_id="RUN-test",
        stdin=io.StringIO("\n  \nok\n"),
        stdout=out,
    )
    assert [json.loads(line) for line in out.getvalue().splitlines()] == [{"id": 1}]
