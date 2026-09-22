"""Render canonical JSON artifacts to Markdown for human review.

Markdown is a generated view only. JSON artifacts remain the single source of truth.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

GENERATED_HEADER = (
    "<!-- GENERATED FILE. DO NOT EDIT. "
    "Source of truth: {source}. Regenerate with `sdlc render`." " -->"
)


def _meta(instance: dict[str, Any]) -> str:
    lines = ["| Поле | Значение |", "|---|---|"]
    lines.append(f"| Artifact | `{instance.get('artifact_type')}` |")
    lines.append(f"| ID | `{instance.get('id')}` |")
    lines.append(f"| Schema | `{instance.get('schema_version')}` |")
    lines.append(f"| Created at | {instance.get('created_at')} |")
    created_by = instance.get("created_by") or {}
    if created_by:
        lines.append(f"| Created by | {created_by.get('id')} ({created_by.get('role')}) |")
    if instance.get("run_id"):
        lines.append(f"| Run ID | `{instance['run_id']}` |")
    if instance.get("status"):
        lines.append(f"| Status | `{instance['status']}` |")
    return "\n".join(lines)


def _links(instance: dict[str, Any]) -> str:
    links = instance.get("links") or []
    if not links:
        return ""
    lines = ["## Links", "", "| Relation | Reference |", "|---|---|"]
    lines += [f"| {link['rel']} | `{link['href']}` |" for link in links]
    return "\n".join(lines)


def _approval(instance: dict[str, Any]) -> str:
    approval = instance.get("approval")
    if not approval:
        return ""
    state = "approved" if approval.get("approved") else "not approved"
    by = (approval.get("by") or {}).get("id", "?")
    lines = ["## Approval", "", f"- State: **{state}**", f"- By: {by} at {approval.get('at')}"]
    if approval.get("solo_override"):
        lines.append(f"- `solo_override=true`: {approval.get('solo_override_reason', '')}")
    if approval.get("note"):
        lines.append(f"- Note: {approval['note']}")
    return "\n".join(lines)


def _render_idea(instance: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# Idea: {instance['title']}",
            "",
            _meta(instance),
            "",
            "## Problem",
            instance["problem"],
            "",
            "## Actor & goal",
            instance["actor_goal"],
            "",
            (
                f"Source: `{instance['source'].get('kind')}` "
                f"(trust tier: `{instance['source'].get('trust_tier')}`)"
            ),
        ]
    )


def _render_specification(instance: dict[str, Any]) -> str:
    out = [f"# Specification: {instance['id']}", "", _meta(instance), ""]
    actor_goal = instance["actor_goal"]
    out += ["## Actor & goal", f"- Actors: {', '.join(actor_goal['actors'])}", f"- Goal: {actor_goal['goal']}", ""]
    scope = instance["scope_boundary"]
    out += ["## Scope boundary", "**In scope**", *[f"- {s}" for s in scope["in_scope"]], "", "**Out of scope**", *[f"- {s}" for s in scope["out_of_scope"]], ""]
    out += ["## Data model", "| Entity | Fields |", "|---|---|"]
    out += [f"| {e['entity']} | {', '.join(e['fields'])} |" for e in instance["data_model"]]
    out += ["", "## API contract", "| Operation | Kind | Summary |", "|---|---|---|"]
    out += [f"| `{op['operation_id']}` | {op['kind']} | {op['summary']} |" for op in instance["api_contract"]]
    out += ["", "## State / lifecycle", "| From | To | Actor |", "|---|---|---|"]
    out += [f"| {t['from']} | {t['to']} | {t['actor']} |" for t in instance["state_lifecycle"]]
    out += ["", "## Acceptance criteria", "| Requirement | Criterion | Verification |", "|---|---|---|"]
    out += [f"| `{ac['requirement_id']}` | {ac['criterion']} | {ac.get('verification', '')} |" for ac in instance["acceptance_criteria"]]
    out += ["", "## Non-goals", *[f"- {n}" for n in instance["non_goals"]]]
    return "\n".join(out)


def _render_threat_model(instance: dict[str, Any]) -> str:
    out = [f"# Threat Model: {instance['id']}", "", _meta(instance), "", f"Method: **{instance['method']}**", ""]
    out += ["## Data flows", "| ID | From | To | Data | Crosses trust boundary |", "|---|---|---|---|---|"]
    out += [f"| {f['id']} | {f['from']} | {f['to']} | {', '.join(f['data'])} | {f['crosses_trust_boundary']} |" for f in instance["data_flows"]]
    out += ["", "## Risks (STRIDE)", "| ID | Category | Severity | Scenario | Control | Verification test |", "|---|---|---|---|---|---|"]
    out += [f"| `{r['id']}` | {r['category']} | **{r['severity']}** | {r['scenario']} | `{r['control_id']}` | {r['verification_test']} |" for r in instance["risks"]]
    return "\n".join(out)


def _render_plan(instance: dict[str, Any]) -> str:
    out = [f"# Implementation Plan: {instance['id']}", "", _meta(instance), "", "## Slices", "| Slice | Title | Requirements | Controls | Depends on |", "|---|---|---|---|---|"]
    out += [f"| {s['slice_id']} | {s['title']} | {', '.join('`'+r+'`' for r in s['requirement_ids'])} | {', '.join('`'+c+'`' for c in s['control_ids'])} | {', '.join(s.get('depends_on', []))} |" for s in instance["slices"]]
    return "\n".join(out)


def _render_task(instance: dict[str, Any]) -> str:
    out = [f"# Task: {instance['title']}", "", _meta(instance), ""]
    out += [f"- Feature: `{instance['feature_id']}`", f"- Plan: `{instance['plan_id']}`", f"- Branch: `{instance.get('branch', 'n/a')}`", ""]
    out += ["## Requirements", *[f"- `{r}`" for r in instance["requirement_ids"]], ""]
    if instance["control_ids"]:
        out += ["## Controls", *[f"- `{c}`" for c in instance["control_ids"]], ""]
    out += ["## Contract changes", *[f"- {c}" for c in instance["contract_changes"]], ""]
    out += ["## Code changes", *[f"- {c}" for c in instance["code_changes"]], ""]
    out += ["## Tests", "| Kind | Ref | Requirement |", "|---|---|---|"]
    out += [f"| {t['kind']} | `{t['ref']}` | `{t['requirement_id']}` |" for t in instance["tests"]]
    return "\n".join(out)


def _render_review(instance: dict[str, Any]) -> str:
    out = [f"# Review: {instance['id']}", "", _meta(instance), "", f"Task: `{instance['task_id']}`  ", f"Subject digest: `{instance['subject_digest']}`", "", f"**Verdict: {instance['verdict']}**", "", "## Findings", "| ID | Severity | Summary |", "|---|---|---|"]
    out += [f"| `{f['id']}` | {f['severity']} | {f['summary']} |" for f in instance["findings"]] or ["| - | - | none |"]
    return "\n".join(out)


def _render_security_review(instance: dict[str, Any]) -> str:
    out = [f"# Security Review: {instance['id']}", "", _meta(instance), "", f"Threat model: `{instance['threat_model_id']}`", "", f"**Verdict: {instance['verdict']}**", "", "## Risk dispositions", "| Risk | Severity | Disposition | Waiver |", "|---|---|---|---|"]
    out += [f"| `{r['risk_id']}` | {r['severity']} | {r['disposition']} | `{r.get('waiver_id', '-')}` |" for r in instance["risk_dispositions"]]
    return "\n".join(out)


def _render_policy_decision(instance: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# Policy Decision: {instance['id']}",
            "",
            _meta(instance),
            "",
            f"- Point: `{instance['point']}`",
            f"- Decision: **{instance['decision']}**",
            f"- Reason codes: {', '.join('`'+c+'`' for c in instance['reason_codes'])}",
            f"- Bundle: `{instance['policy_bundle_version']}`",
            f"- Input digest: `{instance['input_digest']}`",
        ]
    )


def _render_evidence_record(instance: dict[str, Any]) -> str:
    out = [f"# Evidence Record: {instance['id']}", "", _meta(instance), "", f"- Action: {instance['action']}", f"- Trust tier: `{instance['trust_tier']}`", f"- Sensitivity: `{instance['sensitivity']}`"]
    if instance.get("artifact_digest"):
        out.append(f"- Artifact digest: `{instance['artifact_digest']}`")
    compression = instance.get("compression")
    if compression and compression.get("applied"):
        out.append(f"- Compression: `{compression.get('original_size_bytes')}` -> `{compression.get('compressed_size_bytes')}` bytes, handle `{compression.get('recovery_handle')}`")
    return "\n".join(out)


def _render_waiver(instance: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# Waiver: {instance['id']}",
            "",
            _meta(instance),
            "",
            f"- Risk: `{instance['risk_id']}` (severity: {instance['severity']})",
            f"- Justification: {instance['justification']}",
            f"- Compensating control: {instance['compensating_control']}",
            f"- Owner: {(instance['owner'] or {}).get('id')}",
            f"- Expires at: {instance['expires_at']}",
            f"- Approved by: {(instance['approved_by'] or {}).get('id')}",
        ]
    )


def _render_baseline(instance: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# Architecture Baseline: {instance['baseline_id']}",
            "",
            f"- Version: {instance['version']}",
            f"- Status: {instance['status']}",
            f"- Profile: **{instance['profile']}**",
            f"- Approved by: {', '.join(instance['approved_by'])}",
            f"- Approved at: {instance['approved_at']}",
            "",
            "Машиночитаемый источник: `baseline.json`.",
        ]
    )


_RENDERERS: dict[str, Callable[[dict[str, Any]], str]] = {
    "idea": _render_idea,
    "specification": _render_specification,
    "threat-model": _render_threat_model,
    "plan": _render_plan,
    "task": _render_task,
    "review": _render_review,
    "security-review": _render_security_review,
    "policy-decision": _render_policy_decision,
    "evidence-record": _render_evidence_record,
    "waiver": _render_waiver,
    "baseline": _render_baseline,
}


def render_artifact(instance: dict[str, Any], source: str = "artifact.json") -> str:
    if "artifact_type" not in instance and "baseline_id" in instance:
        artifact_type: Any = "baseline"
    else:
        artifact_type = instance.get("artifact_type")
    renderer = _RENDERERS.get(str(artifact_type))
    if renderer is None:
        raise ValueError(f"no renderer for artifact_type={artifact_type!r}")
    body = renderer(instance)
    extras = [section for section in (_links(instance), _approval(instance)) if section]
    if extras:
        body = body + "\n\n" + "\n\n".join(extras)
    return GENERATED_HEADER.format(source=source) + "\n\n" + body + "\n"
