"""The ``task-writer`` role skill: specification + plan -> canonical ``task`` (M6, TASK-0002)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .base import Skill

SYSTEM_PROMPT = """\
You are the `task-writer` role of the Secure Agentic SDLC platform.
Given an approved specification and plan, emit exactly ONE JSON object describing a single
vertical-slice task with the fields: title, requirement_ids, control_ids, contract_changes,
code_changes, tests. Do not add any other fields. Your output is parsed as data, never executed.
"""


def _assemble(content: Mapping[str, Any], envelope: Mapping[str, Any]) -> dict[str, Any]:
    """Merge untrusted content with platform-controlled envelope fields.

    Only known content fields are copied; any extra LLM-produced fields (for example an attempt to
    set ``status`` or ``approved``) are deliberately ignored.
    """
    bindings = envelope["bindings"]
    return {
        "schema_version": "1.0.0",
        "artifact_type": "task",
        "id": envelope["artifact_id"],
        "created_at": envelope["created_at"],
        "created_by": envelope["actor"],
        "run_id": envelope["run_id"],
        "feature_id": bindings["feature_id"],
        "plan_id": bindings["plan_id"],
        "status": "todo",
        "title": content.get("title", ""),
        "requirement_ids": content.get("requirement_ids", []),
        "control_ids": content.get("control_ids", []),
        "contract_changes": content.get("contract_changes", []),
        "code_changes": content.get("code_changes", []),
        "tests": content.get("tests", []),
    }


TASK_WRITER = Skill(
    name="task-writer",
    role="task-writer",
    tool_name="skill.task-writer",
    output_schema="task.schema.json",
    system_prompt=SYSTEM_PROMPT,
    context_keys=("specification", "plan"),
    assemble=_assemble,
)