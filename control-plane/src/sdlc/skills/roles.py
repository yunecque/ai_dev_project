"""Role skills for specification, threat-model, plan, and review (M6, TASK-0003).

Each skill declares its output contract and merges platform-controlled envelope fields with
untrusted LLM content. Only known content fields are copied; injected fields are ignored.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .base import Skill

GRILL_PROMPT = """\
You are the `grill` role of the Secure Agentic SDLC platform.
From an idea, emit exactly ONE JSON object with fields: actor_goal {actors, goal}, scope_boundary
{in_scope, out_of_scope}, data_model, api_contract, state_lifecycle, dependencies, non_goals,
acceptance_criteria. Do not add other fields. Your output is parsed as data, never executed.
"""

GRILL_SECURITY_PROMPT = """\
You are the `grill-security` role of the Secure Agentic SDLC platform.
From an approved specification, perform STRIDE and emit exactly ONE JSON object with fields:
data_flows and risks (each risk: id, category, scenario, severity, control_id, verification_test).
Do not add other fields. Your output is parsed as data, never executed.
"""

PLANNER_PROMPT = """\
You are the `planner` role of the Secure Agentic SDLC platform.
From an approved specification and threat-model, emit exactly ONE JSON object with a `slices` array
(each slice: slice_id, title, requirement_ids, control_ids, optional depends_on/notes).
Do not add other fields. Your output is parsed as data, never executed.
"""

REVIEWER_PROMPT = """\
You are the `reviewer` role of the Secure Agentic SDLC platform.
Emit exactly ONE JSON object with fields: verdict (approved|changes_requested) and findings
(each finding: id, severity, summary, optional location). Do not add other fields.
Your output is parsed as data, never executed.
"""


def _envelope(artifact_type: str, status: str, envelope: Mapping[str, Any]) -> dict[str, Any]:
    bindings = envelope["bindings"]
    base: dict[str, Any] = {
        "schema_version": "1.0.0",
        "artifact_type": artifact_type,
        "id": envelope["artifact_id"],
        "created_at": envelope["created_at"],
        "created_by": envelope["actor"],
        "run_id": envelope["run_id"],
        "feature_id": bindings["feature_id"],
        "status": status,
    }
    return base


def _assemble_specification(content: Mapping[str, Any], envelope: Mapping[str, Any]) -> dict[str, Any]:
    document = _envelope("specification", "draft", envelope)
    document.update(
        {
            "actor_goal": content.get("actor_goal", {"actors": [], "goal": ""}),
            "scope_boundary": content.get("scope_boundary", {"in_scope": [], "out_of_scope": []}),
            "data_model": content.get("data_model", []),
            "api_contract": content.get("api_contract", []),
            "state_lifecycle": content.get("state_lifecycle", []),
            "dependencies": content.get("dependencies", []),
            "non_goals": content.get("non_goals", []),
            "acceptance_criteria": content.get("acceptance_criteria", []),
        }
    )
    return document


def _assemble_threat_model(content: Mapping[str, Any], envelope: Mapping[str, Any]) -> dict[str, Any]:
    document = _envelope("threat-model", "draft", envelope)
    document.update(
        {
            "method": "STRIDE",
            "data_flows": content.get("data_flows", []),
            "risks": content.get("risks", []),
        }
    )
    return document


def _assemble_plan(content: Mapping[str, Any], envelope: Mapping[str, Any]) -> dict[str, Any]:
    document = _envelope("plan", "draft", envelope)
    document["slices"] = content.get("slices", [])
    return document


def _assemble_review(content: Mapping[str, Any], envelope: Mapping[str, Any]) -> dict[str, Any]:
    bindings = envelope["bindings"]
    document: dict[str, Any] = {
        "schema_version": "1.0.0",
        "artifact_type": "review",
        "id": envelope["artifact_id"],
        "created_at": envelope["created_at"],
        "created_by": envelope["actor"],
        "run_id": envelope["run_id"],
        "task_id": bindings["task_id"],
        "subject_digest": bindings["subject_digest"],
        "verdict": content.get("verdict", "changes_requested"),
        "findings": content.get("findings", []),
    }
    return document


GRILL = Skill(
    name="grill",
    role="grill",
    tool_name="skill.grill",
    output_schema="specification.schema.json",
    system_prompt=GRILL_PROMPT,
    context_keys=("idea",),
    assemble=_assemble_specification,
)

GRILL_SECURITY = Skill(
    name="grill-security",
    role="grill-security",
    tool_name="skill.grill-security",
    output_schema="threat-model.schema.json",
    system_prompt=GRILL_SECURITY_PROMPT,
    context_keys=("specification",),
    assemble=_assemble_threat_model,
)

PLANNER = Skill(
    name="planner",
    role="planner",
    tool_name="skill.planner",
    output_schema="plan.schema.json",
    system_prompt=PLANNER_PROMPT,
    context_keys=("specification", "threat-model"),
    assemble=_assemble_plan,
)

REVIEWER = Skill(
    name="reviewer",
    role="reviewer",
    tool_name="skill.reviewer",
    output_schema="review.schema.json",
    system_prompt=REVIEWER_PROMPT,
    context_keys=("task",),
    assemble=_assemble_review,
)
