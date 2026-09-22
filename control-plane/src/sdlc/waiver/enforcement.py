"""Waiver mechanics for findings (M2, TASK-0004).

Enforces the waiver rules from ``docs/evidence-model.md``:

- Critical/High always block merge and deployment, with no exceptions.
- Medium may be temporarily waived by an active, non-expired waiver that was
  approved by an independent security reviewer.
- Low does not block.
- Agents (and CI) may never create, approve, extend, or apply waivers.
- An expired (or revoked) waiver automatically restores the block.

All checks are fail-closed: unknown severity or an invalid waiver blocks.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

SEVERITY_CRITICAL = "critical"
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"

SECURITY_REVIEWER_ROLE = "security-reviewer"

_WAIVABLE_SEVERITIES = frozenset({SEVERITY_MEDIUM})

REASON_AGENT_MAY_NOT_CREATE = "AGENT_MAY_NOT_CREATE"
REASON_AGENT_MAY_NOT_APPROVE = "AGENT_MAY_NOT_APPROVE"
REASON_APPROVER_NOT_SECURITY_REVIEWER = "APPROVER_NOT_SECURITY_REVIEWER"
REASON_APPROVER_IS_RISK_OWNER = "APPROVER_IS_RISK_OWNER"
REASON_EXPIRES_BEFORE_CREATED = "EXPIRES_BEFORE_CREATED"
REASON_SEVERITY_NOT_WAIVABLE = "SEVERITY_NOT_WAIVABLE"
REASON_WAIVER_EXPIRED = "WAIVER_EXPIRED"
REASON_WAIVER_REVOKED = "WAIVER_REVOKED"
REASON_WAIVER_MISSING = "WAIVER_MISSING"
REASON_CRITICAL_NEVER_WAIVED = "CRITICAL_NEVER_WAIVED"
REASON_HIGH_NEVER_WAIVED = "HIGH_NEVER_WAIVED"
REASON_INVALID_WAIVER = "INVALID_WAIVER"


@dataclass(frozen=True)
class WaiverCheck:
    """Result of validating and applying a single waiver."""

    valid: bool
    state: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class BlockDecision:
    """Whether a finding blocks merge/deployment, with machine-readable reasons."""

    blocked: bool
    reason_codes: tuple[str, ...]


def parse_timestamp(value: str) -> datetime:
    """Parse an RFC3339 timestamp (accepts a trailing ``Z``); assume UTC when naive."""
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _as_utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment


def is_waivable(severity: str) -> bool:
    """Only Medium findings can be waived."""
    return severity in _WAIVABLE_SEVERITIES


def may_manage_waiver(actor: Mapping[str, Any]) -> bool:
    """Only humans may create/approve/extend/apply a waiver; agents and CI never can."""
    return actor.get("type") == "human"


def validate_waiver(waiver: Mapping[str, Any], *, now: datetime) -> list[str]:
    """Return reason codes for a structurally or semantically invalid waiver (empty when valid).

    ``now`` is accepted for interface symmetry; time-dependent blocking is reported by
    :func:`waiver_state` / :func:`check_waiver`.
    """
    del now
    reasons: list[str] = []

    if not is_waivable(str(waiver.get("severity", ""))):
        reasons.append(REASON_SEVERITY_NOT_WAIVABLE)

    created_by: Mapping[str, Any] = waiver.get("created_by") or {}
    approved_by: Mapping[str, Any] = waiver.get("approved_by") or {}
    owner: Mapping[str, Any] = waiver.get("owner") or {}

    if created_by.get("type") != "human":
        reasons.append(REASON_AGENT_MAY_NOT_CREATE)
    if approved_by.get("type") != "human":
        reasons.append(REASON_AGENT_MAY_NOT_APPROVE)
    if approved_by.get("role") != SECURITY_REVIEWER_ROLE:
        reasons.append(REASON_APPROVER_NOT_SECURITY_REVIEWER)
    elif owner.get("role") == SECURITY_REVIEWER_ROLE:
        # Separation of duties: the risk owner must not be the security reviewer.
        reasons.append(REASON_APPROVER_IS_RISK_OWNER)

    try:
        created_at = parse_timestamp(str(waiver["created_at"]))
        expires_at = parse_timestamp(str(waiver["expires_at"]))
    except (KeyError, ValueError):
        reasons.append(REASON_INVALID_WAIVER)
    else:
        if expires_at <= created_at:
            reasons.append(REASON_EXPIRES_BEFORE_CREATED)

    return reasons


def waiver_state(waiver: Mapping[str, Any], *, now: datetime) -> str:
    """Return ``active`` | ``expired`` | ``revoked`` | ``invalid``."""
    status = str(waiver.get("status", "active"))
    if status != "active":
        return status
    try:
        expires_at = parse_timestamp(str(waiver["expires_at"]))
    except (KeyError, ValueError):
        return "invalid"
    if _as_utc(now) >= expires_at:
        return "expired"
    return "active"


def check_waiver(waiver: Mapping[str, Any], *, now: datetime) -> WaiverCheck:
    """Validate a waiver and report whether it is currently in force."""
    reasons = list(validate_waiver(waiver, now=now))
    state = waiver_state(waiver, now=now)
    if state == "expired":
        reasons.append(REASON_WAIVER_EXPIRED)
    elif state == "revoked":
        reasons.append(REASON_WAIVER_REVOKED)
    elif state != "active":
        reasons.append(REASON_INVALID_WAIVER)
    return WaiverCheck(valid=not reasons, state=state, reason_codes=tuple(reasons))


def evaluate_risk(
    risk_id: str,
    severity: str,
    waivers: Sequence[Mapping[str, Any]],
    *,
    now: datetime,
) -> BlockDecision:
    """Decide whether a finding blocks, applying the waiver rules fail-closed."""
    if severity == SEVERITY_CRITICAL:
        return BlockDecision(blocked=True, reason_codes=(REASON_CRITICAL_NEVER_WAIVED,))
    if severity == SEVERITY_HIGH:
        return BlockDecision(blocked=True, reason_codes=(REASON_HIGH_NEVER_WAIVED,))
    if severity == SEVERITY_LOW:
        return BlockDecision(blocked=False, reason_codes=())
    if severity != SEVERITY_MEDIUM:
        return BlockDecision(blocked=True, reason_codes=(REASON_SEVERITY_NOT_WAIVABLE,))

    matching = [waiver for waiver in waivers if str(waiver.get("risk_id", "")) == risk_id]
    if not matching:
        return BlockDecision(blocked=True, reason_codes=(REASON_WAIVER_MISSING,))

    collected: list[str] = []
    for waiver in matching:
        check = check_waiver(waiver, now=now)
        if check.valid:
            return BlockDecision(blocked=False, reason_codes=())
        collected.extend(check.reason_codes)
    return BlockDecision(blocked=True, reason_codes=tuple(dict.fromkeys(collected)))