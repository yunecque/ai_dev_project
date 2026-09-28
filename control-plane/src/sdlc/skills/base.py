"""Role skills: trusted prompt + output contract over an untrusted LLM (M6, TASK-0002).

A skill declares the artifact type it produces and how to assemble the final document from
untrusted LLM content plus platform-controlled envelope fields. The LLM output is parsed as data
and schema-validated; any instruction-like content is ignored.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ..evidence.pipeline import SensitiveContentError
from ..trust import TrustTier, classify_source


class SkillError(ValueError):
    """Raised when an LLM output cannot be parsed into a skill artifact (fail-closed)."""


@dataclass(frozen=True)
class ContextInput:
    """A trusted input document plus its source kind (classified into a trust tier)."""

    name: str
    document: Mapping[str, Any]
    source: str = "approved_artifact"


AssembleFn = Callable[[Mapping[str, Any], Mapping[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class Skill:
    """Declarative role skill contract."""

    name: str
    role: str
    tool_name: str
    output_schema: str
    system_prompt: str
    context_keys: tuple[str, ...]
    assemble: AssembleFn


def add_links(document: dict[str, Any], links: Sequence[Mapping[str, str]]) -> None:
    """Attach informational links to an assembled artifact (deduplicated by href)."""
    existing: list[dict[str, str]] = [dict(link) for link in document.get("links", [])]
    seen = {str(link.get("href", "")) for link in existing}
    for link in links:
        href = str(link.get("href", ""))
        if href in seen:
            continue
        seen.add(href)
        existing.append({"rel": str(link["rel"]), "href": href})
    document["links"] = existing


def build_context(inputs: Sequence[ContextInput]) -> dict[str, Any]:
    """Return the model context, rejecting any sensitive input (ADR-0007)."""
    context: dict[str, Any] = {}
    for item in inputs:
        if classify_source(item.source) is TrustTier.SENSITIVE:
            raise SensitiveContentError(
                f"input {item.name!r} is sensitive and must not enter the model context"
            )
        context[item.name] = dict(item.document)
    return context


def extract_json(text: str) -> dict[str, Any]:
    """Extract a JSON object from untrusted model text; fail closed on anything else."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    candidates = [stripped]
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end > start:
        candidates.append(stripped[start : end + 1])
    for candidate in candidates:
        try:
            parsed: Any = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise SkillError("LLM output is not a JSON object")