"""Tests for the allowlisted command runner (M6, panel-run checks)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from sdlc.tools import (
    DEFAULT_ALLOWED_PROGRAMS,
    CommandRunner,
    ToolRegistry,
    register_test_tools,
)


def _completed(code: int = 0, out: str = "", err: str = "") -> Any:
    return SimpleNamespace(returncode=code, stdout=out, stderr=err)


def test_runs_allowlisted_program_in_root(tmp_path: Path) -> None:
    calls: dict[str, Any] = {}

    def fake_run(argv: list[str], **kwargs: Any) -> Any:
        calls["argv"] = argv
        calls["kwargs"] = kwargs
        return _completed(code=0, out="2 passed")

    runner = CommandRunner(tmp_path, allowlist=("pytest",), run=fake_run)
    result = runner.execute(["pytest", "-q"])
    assert result == {"exit_code": 0, "stdout": "2 passed", "stderr": "", "truncated": False}
    assert calls["argv"] == ["pytest", "-q"]
    assert calls["kwargs"]["shell"] is False
    assert calls["kwargs"]["cwd"] == tmp_path.resolve()


def test_nonzero_exit_is_surfaced(tmp_path: Path) -> None:
    runner = CommandRunner(
        tmp_path, allowlist=("pytest",), run=lambda argv, **kwargs: _completed(code=1, err="boom")
    )
    result = runner.execute(["pytest"])
    assert result["exit_code"] == 1
    assert result["stderr"] == "boom"


def test_rejects_program_outside_allowlist(tmp_path: Path) -> None:
    runner = CommandRunner(tmp_path, allowlist=("pytest",), run=lambda argv, **kwargs: _completed())
    with pytest.raises(ValueError):
        runner.execute(["bash", "-c", "rm -rf /"])


def test_rejects_path_in_program_name(tmp_path: Path) -> None:
    runner = CommandRunner(tmp_path, allowlist=("pytest",), run=lambda argv, **kwargs: _completed())
    with pytest.raises(ValueError):
        runner.execute(["/usr/bin/pytest"])
    with pytest.raises(ValueError):
        runner.execute(["./pytest"])


def test_rejects_empty_argv(tmp_path: Path) -> None:
    runner = CommandRunner(tmp_path, allowlist=("pytest",), run=lambda argv, **kwargs: _completed())
    with pytest.raises(ValueError):
        runner.execute([])


def test_cwd_is_confined_to_root(tmp_path: Path) -> None:
    calls: dict[str, Any] = {}

    def fake_run(argv: list[str], **kwargs: Any) -> Any:
        calls["cwd"] = kwargs["cwd"]
        return _completed()

    (tmp_path / "control-plane").mkdir()
    runner = CommandRunner(tmp_path, allowlist=("mypy",), run=fake_run)
    runner.execute(["mypy"], cwd="control-plane")
    assert calls["cwd"] == (tmp_path / "control-plane").resolve()


def test_rejects_cwd_escape(tmp_path: Path) -> None:
    runner = CommandRunner(tmp_path, allowlist=("mypy",), run=lambda argv, **kwargs: _completed())
    with pytest.raises(ValueError):
        runner.execute(["mypy"], cwd="../outside")


def test_truncates_large_output(tmp_path: Path) -> None:
    runner = CommandRunner(
        tmp_path, allowlist=("pytest",), run=lambda argv, **kwargs: _completed(out="x" * 30000)
    )
    result = runner.execute(["pytest"])
    assert result["truncated"] is True
    assert len(result["stdout"]) == 20000


def test_register_test_tools_adds_run_tests(tmp_path: Path) -> None:
    registry = ToolRegistry()
    register_test_tools(registry, tmp_path, allowlist=("pytest",))
    spec = registry.get("run_tests")
    assert spec.scope == "workspace"
    assert spec.args_schema["required"] == ["argv"]


def test_default_allowlist_covers_required_checks() -> None:
    for program in ("pytest", "ruff", "mypy", "opa"):
        assert program in DEFAULT_ALLOWED_PROGRAMS
