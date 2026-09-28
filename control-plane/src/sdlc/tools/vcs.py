"""Policy-gated VCS tool: prepare a branch/commit and open a pull request (M6, TASK-0009).

The agent has no shell and no git credentials. It can still land work by calling the
allowlisted ``open_pr`` tool, which the platform executes: OPA ``pre-tool-call`` first, then a
scoped ``vcs`` capability, then this handler. Git runs with a fixed argv and ``shell=False``;
the GitHub token lives only in the panel environment and never enters the model context or the
evidence record. Failures are fail-closed: bad branch names, path escapes, and protected-zone
paths are rejected before any git or network call is made.

The flow is idempotent: an existing branch is switched to (not recreated), an already-committed
change is not re-committed, and a pull request that already exists is returned instead of
failing, so a retry after a transient error is safe.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .registry import ToolRegistry, ToolSpec

# feature/{FEATURE_ID}-{TASK_ID}-slug, e.g. feature/FEAT-0006-TASK-0009-open-pr-tool
BRANCH_PATTERN = re.compile(
    r"^feature/[A-Z][A-Z0-9]*-\d+-[A-Z][A-Z0-9]*-\d+-[a-z0-9][a-z0-9-]*$"
)
GIT_TIMEOUT_SECONDS = 120
GITHUB_TIMEOUT_SECONDS = 30

# Mirror of ``protected_paths`` in policies/pre_tool_call.rego. Defence in depth on top of OPA:
# keep in sync when the policy list changes.
PROTECTED_PATH_MARKERS = (
    ".github/",
    "contracts/",
    "policies/",
    "security/",
    "infra/",
    "specs/",
    ".opencode/",
    "docs/adr/",
    "docs/roadmap.md",
    "baseline.json",
    "ARCHITECTURE_BASELINE.md",
)

OPEN_PR_SCHEMA = {
    "type": "object",
    "required": ["branch", "commit_message", "paths"],
    "properties": {
        "branch": {"type": "string"},
        "commit_message": {"type": "string", "minLength": 1},
        "paths": {"type": "array", "items": {"type": "string"}, "minItems": 1},
        "base": {"type": "string"},
        "title": {"type": "string"},
        "body": {"type": "string"},
    },
    "additionalProperties": False,
}
OPEN_PR_RESULT = {
    "type": "object",
    "required": ["branch", "commit", "pr_url"],
    "properties": {
        "branch": {"type": "string"},
        "commit": {"type": "string"},
        "pr_url": {"type": "string"},
    },
}

GitCallable = Callable[[Sequence[str], Path], str]
PullRequestCallable = Callable[[Mapping[str, Any]], str]


def _run_git(argv: Sequence[str], cwd: Path) -> str:
    """Run ``git argv`` with a fixed argv and ``shell=False``; fail closed on non-zero exit."""
    try:
        completed = subprocess.run(
            ["git", *argv],
            cwd=cwd,
            shell=False,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f"git failed: {exc}") from exc
    if completed.returncode != 0:
        raise ValueError(f"git {' '.join(argv)} failed: {completed.stderr.strip()}")
    return completed.stdout


def _github_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _github_credentials() -> tuple[str, str]:
    token = os.environ.get("SDLC_GITHUB_TOKEN")
    repo = os.environ.get("SDLC_GITHUB_REPOSITORY")
    if not token or not repo:
        raise ValueError("SDLC_GITHUB_TOKEN and SDLC_GITHUB_REPOSITORY are required")
    return token, repo


def _find_existing_pull_request(repo: str, branch: str, headers: Mapping[str, str]) -> str:
    """Return the html_url of an open PR whose head is ``branch``, or the empty string."""
    owner = repo.split("/", 1)[0]
    query = urllib.parse.urlencode({"state": "open", "head": f"{owner}:{branch}"})
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/pulls?{query}", headers=dict(headers), method="GET"
    )
    try:
        with urllib.request.urlopen(request, timeout=GITHUB_TIMEOUT_SECONDS) as response:
            data: Any = json.loads(response.read())
    except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError):
        return ""
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return str(data[0].get("html_url", ""))
    return ""


def _open_github_pull_request(payload: Mapping[str, Any]) -> str:
    """Open a pull request via the GitHub REST API using a panel-held token (idempotent)."""
    token, repo = _github_credentials()
    headers = _github_headers(token)
    body = json.dumps(
        {
            "title": payload["title"],
            "head": payload["branch"],
            "base": payload["base"],
            "body": payload["body"],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/pulls", data=body, method="POST", headers=headers
    )
    try:
        with urllib.request.urlopen(request, timeout=GITHUB_TIMEOUT_SECONDS) as response:
            data: Any = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        # 422 means "a pull request already exists" for this head: return it instead of failing.
        if exc.code == 422:
            existing = _find_existing_pull_request(repo, str(payload["branch"]), headers)
            if existing:
                return existing
        raise ValueError(f"failed to open pull request: HTTP {exc.code}") from exc
    except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
        raise ValueError(f"failed to open pull request: {exc}") from exc
    if not isinstance(data, dict) or not data.get("html_url"):
        raise ValueError("pull request response is missing html_url")
    return str(data["html_url"])


class OpenPRTool:
    """Branch + commit the given paths, push, and open a pull request (idempotent)."""

    def __init__(
        self,
        root: Path,
        *,
        git: GitCallable | None = None,
        open_pull_request: PullRequestCallable | None = None,
    ) -> None:
        self._root = Path(root).resolve()
        self._git = git or _run_git
        self._open = open_pull_request or _open_github_pull_request

    def __call__(self, args: Mapping[str, Any]) -> Mapping[str, Any]:
        branch = self._branch(str(args["branch"]))
        message = str(args["commit_message"])
        if not message.strip():
            raise ValueError("commit_message must be non-empty")
        paths = [self._confine(str(path)) for path in args["paths"]]
        if not paths:
            raise ValueError("paths must be non-empty")
        self._reject_protected(paths)
        base = str(args.get("base") or "main").strip() or "main"

        self._switch(branch)
        self._git(["add", "--", *paths], self._root)
        if self._git(["diff", "--cached", "--name-only"], self._root).strip():
            self._git(["commit", "-m", message], self._root)
        self._git(["push", "-u", "origin", branch], self._root)
        commit = self._git(["rev-parse", "HEAD"], self._root).strip()

        pr_url = self._open(
            {
                "branch": branch,
                "base": base,
                "title": str(args.get("title") or message.splitlines()[0]),
                "body": str(args.get("body") or ""),
            }
        )
        return {"branch": branch, "commit": commit, "pr_url": pr_url}

    def _switch(self, branch: str) -> None:
        """Switch to ``branch``, creating it only if it does not exist locally."""
        exists = self._git(["branch", "--list", branch], self._root).strip()
        if exists:
            self._git(["switch", branch], self._root)
        else:
            self._git(["switch", "-c", branch], self._root)

    @staticmethod
    def _branch(branch: str) -> str:
        if not BRANCH_PATTERN.match(branch):
            raise ValueError("branch must match feature/{FEATURE_ID}-{TASK_ID}-slug")
        return branch

    def _confine(self, relative_path: str) -> str:
        if not relative_path or relative_path.startswith(("/", "\\")):
            raise ValueError("path must be relative to the workspace root")
        if ".." in Path(relative_path).parts:
            raise ValueError("path must not contain '..'")
        target = (self._root / relative_path).resolve()
        if target != self._root and self._root not in target.parents:
            raise ValueError("path escapes the workspace root")
        return relative_path.replace("\\", "/")

    @staticmethod
    def _reject_protected(paths: Sequence[str]) -> None:
        for path in paths:
            normalized = path.replace("\\", "/")
            for marker in PROTECTED_PATH_MARKERS:
                if marker in normalized:
                    raise ValueError(
                        f"PROTECTED_PR_PATH: {path} touches protected zone {marker!r}"
                    )


def register_vcs_tools(
    registry: ToolRegistry,
    root: Path,
    *,
    git: GitCallable | None = None,
    open_pull_request: PullRequestCallable | None = None,
) -> None:
    """Register the ``open_pr`` tool (branch/commit/push + pull request)."""
    registry.register(
        ToolSpec(
            name="open_pr",
            scope="vcs",
            description=(
                "Create a feature branch, commit the given paths, push it, and open a "
                "pull request against the base branch"
            ),
            args_schema=OPEN_PR_SCHEMA,
            result_schema=OPEN_PR_RESULT,
            handler=OpenPRTool(root, git=git, open_pull_request=open_pull_request),
        )
    )


__all__ = ["PROTECTED_PATH_MARKERS", "OpenPRTool", "register_vcs_tools"]
