"""Role skills (M6, TASK-0002+)."""

from __future__ import annotations

from .base import (
    AssembleFn,
    ContextInput,
    Skill,
    SkillError,
    add_links,
    build_context,
    extract_json,
)
from .registry import SkillRegistry, UnknownSkillError
from .roles import GRILL, GRILL_SECURITY, PLANNER, REVIEWER
from .runner import (
    POLICY_POINT,
    REASON_COMPLETED,
    REASON_INVALID_LLM_OUTPUT,
    REASON_MISSING_CONTEXT,
    REASON_SCHEMA_INVALID,
    REASON_UNKNOWN_SKILL,
    SkillRunner,
    SkillRunResult,
)
from .task_writer import TASK_WRITER

DEFAULT_SKILLS: tuple[Skill, ...] = (GRILL, GRILL_SECURITY, PLANNER, TASK_WRITER, REVIEWER)


def build_default_registry() -> SkillRegistry:
    """Return a registry with every built-in role skill."""
    return SkillRegistry(DEFAULT_SKILLS)


__all__ = [
    "DEFAULT_SKILLS",
    "GRILL",
    "GRILL_SECURITY",
    "PLANNER",
    "POLICY_POINT",
    "REASON_COMPLETED",
    "REASON_INVALID_LLM_OUTPUT",
    "REASON_MISSING_CONTEXT",
    "REASON_SCHEMA_INVALID",
    "REASON_UNKNOWN_SKILL",
    "REVIEWER",
    "TASK_WRITER",
    "AssembleFn",
    "ContextInput",
    "Skill",
    "SkillError",
    "SkillRegistry",
    "SkillRunResult",
    "SkillRunner",
    "UnknownSkillError",
    "add_links",
    "build_context",
    "extract_json",
]