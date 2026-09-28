"""Tests for the policy-gated open_pr tool (M6, TASK-0009).

The tool must be fail-closed: bad branch names, path escapes, and protected-zone paths are
rejected before any git or network call. Tests inject fake git/PR callables so nothing real
is spawned or pushed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from sdlc.evidence import EvidenceStore
from sdlc.policy import PolicyResult
from sdlc.runner import RunnerExecutor, RunRegistry
from sdlc.tools import ToolRegistry, register_vcs_tools

GOOD_BRANCH = "feature/FEAT-0006-TASK-0009-open-pr-tool"
SECRET = b"vcs-secret"
ACTOR = {"type": "agent", "id": "implementer", "role": "implementer"}
CREATED_AT = "2026-09-24T00:00:00Z"


class _FakeGit:
    def __init__(
        self,
        commit: str = "deadbeef",
        *,
        existing: set[str] | None = None,
        staged: str = "changed\n",
    ) -> None:
        self.calls: list[list[str]] = []
        self._commit = commit
        self._existing = existing or set()
        self._staged = staged

    def __call__(self, argv: Sequence[str], cwd: Path) -> str:
        args = list(argv)
        self.calls.append(args)
        if args[:2] == ["rev-parse", "HEAD"]:
            return self._commit + "\n"
        if args[:2] == ["branch", "--list"]:
            return f"  {args[2]}\n" if args[2] in self._existing else ""
        if args[:2] == ["diff", "--cached"]:
            return self._staged
        return ""

    def has(self, *prefix: str) -> bool:
        return any(call[: len(prefix)] == list(prefix) for call in self.calls)


class _FakeOpener:
    def __init__(self, url: str = "https://github.com/o/r/pull/1") -> None:
        self.payloads: list[dict[str, Any]] = []
        self._url = url

    def __call__(self, payload: Mapping[str, Any]) -> str:
        self.payloads.append(dict(payload))
        return self._url


def _tool(tmp_path: Path, git: _FakeGit, opener: _FakeOpener) -> Any:
    registry = ToolRegistry()
    register_vcs_tools(registry, tmp_path, git=git, open_pull_request=opener)
    return registry.get("open_pr")


def test_registers_with_vcs_scope(tmp_path: Path) -> None:
    spec = _tool(tmp_path, _FakeGit(), _FakeOpener())
    assert spec.scope == "vcs"
    assert spec.args_schema["required"] == ["branch", "commit_message", "paths"]


def test_happy_path_branch_commit_push_pr(tmp_path: Path) -> None:
    git, opener = _FakeGit(), _FakeOpener()
    result = _tool(tmp_path, git, opener).handler(
        {
            "branch": GOOD_BRANCH,
            "commit_message": "FEAT-0006/TASK-0009: add open_pr",
            "paths": ["control-plane/src/sdlc/tools/vcs.py"],
            "title": "Add open_pr",
            "body": "body",
        }
    )
    assert result == {
        "branch": GOOD_BRANCH,
        "commit": "deadbeef",
        "pr_url": "https://github.com/o/r/pull/1",
    }
    assert git.has("switch", "-c", GOOD_BRANCH)
    assert git.has("add", "--", "control-plane/src/sdlc/tools/vcs.py")
    assert git.has("commit", "-m", "FEAT-0006/TASK-0009: add open_pr")
    assert git.has("push", "-u", "origin", GOOD_BRANCH)
    assert opener.payloads == [
        {"branch": GOOD_BRANCH, "base": "main", "title": "Add open_pr", "body": "body"}
    ]


def test_retry_is_idempotent(tmp_path: Path) -> None:
    """Existing branch and already-committed change: switch (no -c) and skip the commit."""
    git = _FakeGit(existing={GOOD_BRANCH}, staged="")
    opener = _FakeOpener()
    result = _tool(tmp_path, git, opener).handler(
        {"branch": GOOD_BRANCH, "commit_message": "x", "paths": ["apps/a.go"]}
    )
    assert git.has("switch", GOOD_BRANCH)
    assert not git.has("switch", "-c")
    assert not git.has("commit")
    assert git.has("push", "-u", "origin", GOOD_BRANCH)
    assert result["pr_url"] == "https://github.com/o/r/pull/1"


def test_title_defaults_to_first_commit_line(tmp_path: Path) -> None:
    git, opener = _FakeGit(), _FakeOpener()
    _tool(tmp_path, git, opener).handler(
        {
            "branch": GOOD_BRANCH,
            "commit_message": "FEAT-0006/TASK-0009: summary\n\nmore detail",
            "paths": ["apps/gateway/main.go"],
        }
    )
    assert opener.payloads[0]["title"] == "FEAT-0006/TASK-0009: summary"
    assert opener.payloads[0]["base"] == "main"


def test_rejects_bad_branch(tmp_path: Path) -> None:
    git, opener = _FakeGit(), _FakeOpener()
    with pytest.raises(ValueError):
        _tool(tmp_path, git, opener).handler(
            {"branch": "main", "commit_message": "x", "paths": ["apps/a.go"]}
        )
    assert git.calls == []
    assert opener.payloads == []


def test_rejects_parent_escape(tmp_path: Path) -> None:
    git, opener = _FakeGit(), _FakeOpener()
    with pytest.raises(ValueError):
        _tool(tmp_path, git, opener).handler(
            {"branch": GOOD_BRANCH, "commit_message": "x", "paths": ["../escape.txt"]}
        )
    assert git.calls == []


def test_rejects_absolute_path(tmp_path: Path) -> None:
    git, opener = _FakeGit(), _FakeOpener()
    with pytest.raises(ValueError):
        _tool(tmp_path, git, opener).handler(
            {"branch": GOOD_BRANCH, "commit_message": "x", "paths": ["/etc/passwd"]}
        )
    assert git.calls == []


def test_rejects_protected_zone(tmp_path: Path) -> None:
    git, opener = _FakeGit(), _FakeOpener()
    with pytest.raises(ValueError):
        _tool(tmp_path, git, opener).handler(
            {
                "branch": GOOD_BRANCH,
                "commit_message": "x",
                "paths": ["policies/pre_tool_call.rego"],
            }
        )
    assert git.calls == []
    assert opener.payloads == []


class _RecordingPolicy:
    def __init__(self, allow: bool = True) -> None:
        self.payloads: list[dict[str, Any]] = []
        self._allow = allow

    def evaluate(self, *, point: str, payload: Mapping[str, Any]) -> PolicyResult:
        self.payloads.append(dict(payload))
        codes = ("ALLOWED",) if self._allow else ("DENIED",)
        return PolicyResult(self._allow, codes, "test", "digest")


def test_executor_forwards_all_paths_as_resource(tmp_path: Path) -> None:
    git, opener = _FakeGit(), _FakeOpener()
    tools = ToolRegistry()
    register_vcs_tools(tools, tmp_path, git=git, open_pull_request=opener)
    capabilities = RunRegistry(secret=SECRET)
    run = capabilities.start(ACTOR)
    token = capabilities.issue(run.run_id, tool="open_pr", scope="vcs")
    policy = _RecordingPolicy()
    executor = RunnerExecutor(
        policy=policy,
        capabilities=capabilities,
        tools=tools,
        evidence_store=EvidenceStore(tmp_path),
    )
    result = executor.execute(
        run_id=run.run_id,
        token=token,
        tool="open_pr",
        args={
            "branch": GOOD_BRANCH,
            "commit_message": "FEAT-0006/TASK-0009: x",
            "paths": ["apps/a.go", "apps/b.go"],
        },
        scope="vcs",
        created_at=CREATED_AT,
        decision_id="PD-0008",
        evidence_id="EV-0008",
    )
    assert result.allowed is True
    assert policy.payloads[-1]["path"] == "apps/a.go,apps/b.go"
