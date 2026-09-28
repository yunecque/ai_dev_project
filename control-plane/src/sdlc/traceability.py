"""Portfolio traceability: prove the idea -> specification -> ... -> release chain (M5).

Reads canonical JSON artifacts (trusted after approval), indexes them by repo-relative path and
follows ``links`` to assemble the lifecycle chain for a feature. Reports missing lifecycle stages
and dangling local link targets. Links to non-JSON references (contracts, PR URLs) are
informational and not resolved.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CHAIN_ORDER: tuple[str, ...] = (
    "idea",
    "specification",
    "threat-model",
    "plan",
    "task",
    "review",
    "security-review",
)


@dataclass(frozen=True)
class TraceNode:
    """A single artifact participating in the chain."""

    artifact_id: str
    artifact_type: str
    path: str
    feature_id: str | None


@dataclass(frozen=True)
class Traceability:
    """Outcome of tracing one feature through its canonical artifacts."""

    feature_id: str
    nodes: tuple[TraceNode, ...]
    ordered_types: tuple[str, ...]
    missing_types: tuple[str, ...]
    dangling: tuple[str, ...]

    @property
    def complete(self) -> bool:
        return not self.missing_types and not self.dangling


def _read(path: Path) -> dict[str, Any]:
    data: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{path}: top-level JSON must be an object")
    return data


def load_artifacts(paths: Iterable[Path]) -> dict[Path, dict[str, Any]]:
    """Load the given JSON files, keyed by resolved path."""
    artifacts: dict[Path, dict[str, Any]] = {}
    for path in paths:
        if path.is_file():
            artifacts[path.resolve()] = _read(path)
    return artifacts


def discover(repo_root: Path, *, subdir: str = "specs") -> dict[Path, dict[str, Any]]:
    """Load every JSON artifact under ``repo_root/subdir``."""
    return load_artifacts(sorted((repo_root / subdir).rglob("*.json")))


def _local_link_targets(doc: Mapping[str, Any]) -> list[str]:
    targets: list[str] = []
    for link in doc.get("links", []):
        href = str(link.get("href", ""))
        if href.endswith(".json"):
            targets.append(href)
    return targets


def trace_feature(
    repo_root: Path,
    feature_id: str,
    *,
    artifacts: Mapping[Path, dict[str, Any]] | None = None,
) -> Traceability:
    """Assemble and audit the traceability chain for ``feature_id`` (fail-closed on gaps)."""
    index = dict(artifacts) if artifacts is not None else discover(repo_root)
    by_href = {path.relative_to(repo_root).as_posix(): path for path in index}

    # Reverse edges: some artifacts (e.g. reviews) reference the chain rather than being
    # referenced by it, so trace in both directions to assemble the full picture.
    incoming: dict[Path, list[Path]] = {}
    for path, doc in index.items():
        for href in _local_link_targets(doc):
            target = by_href.get(href)
            if target is not None:
                incoming.setdefault(target, []).append(path)

    selected: set[Path] = {
        path for path, doc in index.items() if doc.get("feature_id") == feature_id
    }
    dangling: list[str] = []

    frontier = list(selected)
    while frontier:
        current = frontier.pop()
        doc = index[current]
        neighbors: list[Path] = []
        for href in _local_link_targets(doc):
            target = by_href.get(href)
            if target is None:
                dangling.append(href)
            else:
                neighbors.append(target)
        neighbors.extend(incoming.get(current, []))
        for neighbor in neighbors:
            if neighbor not in selected:
                selected.add(neighbor)
                frontier.append(neighbor)

    nodes: list[TraceNode] = []
    for path in selected:
        doc = index[path]
        nodes.append(
            TraceNode(
                artifact_id=str(doc.get("id", "")),
                artifact_type=str(doc.get("artifact_type", "")),
                path=path.relative_to(repo_root).as_posix(),
                feature_id=doc.get("feature_id"),
            )
        )
    nodes.sort(key=_node_sort_key)

    present = {node.artifact_type for node in nodes}
    ordered = tuple(kind for kind in CHAIN_ORDER if kind in present)
    missing = tuple(kind for kind in CHAIN_ORDER if kind not in present)
    return Traceability(
        feature_id=feature_id,
        nodes=tuple(nodes),
        ordered_types=ordered,
        missing_types=missing,
        dangling=tuple(sorted(set(dangling))),
    )


def _node_sort_key(node: TraceNode) -> tuple[int, str]:
    rank = CHAIN_ORDER.index(node.artifact_type) if node.artifact_type in CHAIN_ORDER else len(CHAIN_ORDER)
    return rank, node.artifact_id


def format_report(report: Traceability) -> str:
    """Render a human-readable traceability report."""
    status = "COMPLETE" if report.complete else "INCOMPLETE"
    lines = [f"feature {report.feature_id}: {status}"]
    for node in report.nodes:
        lines.append(f"  {node.artifact_type:<16} {node.artifact_id:<12} {node.path}")
    if report.missing_types:
        lines.append(f"  missing: {', '.join(report.missing_types)}")
    if report.dangling:
        lines.append(f"  dangling: {', '.join(report.dangling)}")
    return "\n".join(lines)
