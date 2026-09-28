"""Allowlisted command runner for the agent execution layer (M6).

There is still no arbitrary shell: the caller passes an explicit ``argv`` (never a shell
string), the program name must be on a fixed allowlist, path separators are rejected in
``argv[0]``, and the process runs with ``shell=False`` in a fixed working directory with a
timeout. This gives the agent a controlled way to run the repository's checks
(``pytest``/``ruff``/``mypy``/``opa``) without a shell escape hatch.

Note: running tests executes repository code by definition, so this tool is still
code-execution capability — scoped, non-shell, and auditable (every call is policy-gated and
recorded as evidence by the runner), but not a sandbox. See ``docs/limitations.md``.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .registry import ToolHandler, ToolRegistry, ToolSpec

DEFAULT_ALLOWED_PROGRAMS = ("ruff", "mypy", "pytest", "opa", "gofmt", "go")
DEFAULT_TIMEOUT_SECONDS = 300
MAX_OUTPUT_CHARS = 20000

RUN_SCHEMA = {
    "type": "object",
    "required": ["argv"],
    "properties": {
        "argv": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "cwd": {"type": "string"},
    },
    "additionalProperties": False,
}
RUN_RESULT = {
    "type": "object",
    "required": ["exit_code", "stdout", "stderr", "truncated"],
    "properties": {
        "exit_code": {"type": "integer"},
        "stdout": {"type": "string"},
        "stderr": {"type": "string"},
        "truncated": {"type": "boolean"},
    },
}

RunCallable = Callable[..., Any]


class CommandRunner:
    """Run an allowlisted program with ``shell=False`` and a fixed cwd/timeout."""

    def __init__(
        self,
        root: Path,
        *,
        allowlist: Sequence[str] = DEFAULT_ALLOWED_PROGRAMS,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        run: RunCallable | None = None,
    ) -> None:
        self._root = Path(root).resolve()
        self._allow = set(allowlist)
        self._timeout = timeout
        self._run = run or subprocess.run

    def execute(self, argv: Sequence[str], cwd: str = "") -> dict[str, Any]:
        self._validate(argv)
        completed = self._run(
            list(argv),
            cwd=self._resolve_cwd(cwd),
            shell=False,
            capture_output=True,
            text=True,
            timeout=self._timeout,
        )
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        truncated = len(stdout) > MAX_OUTPUT_CHARS or len(stderr) > MAX_OUTPUT_CHARS
        return {
            "exit_code": int(completed.returncode),
            "stdout": stdout[:MAX_OUTPUT_CHARS],
            "stderr": stderr[:MAX_OUTPUT_CHARS],
            "truncated": truncated,
        }

    def _resolve_cwd(self, cwd: str) -> Path:
        """Resolve the working directory, confined to the workspace root."""
        if cwd in ("", "."):
            return self._root
        if cwd.startswith(("/", "\\")) or ".." in Path(cwd).parts:
            raise ValueError("cwd must be relative to the workspace root")
        target = (self._root / cwd).resolve()
        if target != self._root and self._root not in target.parents:
            raise ValueError("cwd escapes the workspace root")
        if not target.is_dir():
            raise ValueError("cwd is not a directory")
        return target

    def _validate(self, argv: Sequence[str]) -> None:
        if isinstance(argv, (str, bytes)) or not isinstance(argv, Sequence) or not argv:
            raise ValueError("argv must be a non-empty list of strings")
        program = argv[0]
        if not isinstance(program, str) or "/" in program or "\\" in program:
            raise ValueError("program must be a bare name on the allowlist")
        if program not in self._allow:
            raise ValueError(f"program not allowed: {program}")
        for item in argv:
            if not isinstance(item, str):
                raise TypeError("all argv items must be strings")
            if "\x00" in item:
                raise ValueError("argv must not contain NUL")


def _run_handler(runner: CommandRunner) -> ToolHandler:
    def handler(args: Mapping[str, Any]) -> Mapping[str, Any]:
        argv = [str(item) for item in args["argv"]]
        return runner.execute(argv, str(args.get("cwd", "")))

    return handler


def register_test_tools(
    registry: ToolRegistry,
    root: Path,
    *,
    allowlist: Sequence[str] = DEFAULT_ALLOWED_PROGRAMS,
    runner: RunCallable | None = None,
) -> None:
    """Register the ``run_tests`` tool (allowlisted, non-shell command execution)."""
    command_runner = CommandRunner(root, allowlist=allowlist, run=runner)
    registry.register(
        ToolSpec(
            name="run_tests",
            scope="workspace",
            description="Run an allowlisted repository check (pytest/ruff/mypy/opa) via explicit argv",
            args_schema=RUN_SCHEMA,
            result_schema=RUN_RESULT,
            handler=_run_handler(command_runner),
        )
    )


__all__ = [
    "DEFAULT_ALLOWED_PROGRAMS",
    "DEFAULT_TIMEOUT_SECONDS",
    "MAX_OUTPUT_CHARS",
    "CommandRunner",
    "register_test_tools",
]
