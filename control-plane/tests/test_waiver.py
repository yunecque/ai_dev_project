"""Tests for waiver mechanics (M2, TASK-0004).

Rules (docs/evidence-model.md + SPEC/TM golden path):
- Critical/High always block merge/deployment, regardless of waivers.
- Medium can be waived by an active, non-expired, independently approved waiver.
- Low does not block.
- Agents may never create, approve, extend, or apply waivers.
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sdlc.artifacts import find_repo_root
from sdlc.cli import main
from sdlc.waiver import (
    REASON_AGENT_MAY_NOT_APPROVE,
    REASON_AGENT_MAY_NOT_CREATE,
    REASON_APPROVER_IS_RISK_OWNER,
    REASON_APPROVER_NOT_SECURITY_REVIEWER,
    REASON_CRITICAL_NEVER_WAIVED,
    REASON_EXPIRES_BEFORE_CREATED,
    REASON_HIGH_NEVER_WAIVED,
    REASON_WAIVER_EXPIRED,
    REASON_WAIVER_MISSING,
    REASON_WAIVER_REVOKED,
    check_waiver,
    evaluate_risk,
    is_waivable,
    may_manage_waiver,
    validate_waiver,
    waiver_state,
)

REPO_ROOT = find_repo_root()
NOW = datetime(2026, 10, 1, tzinfo=UTC)


def _golden_waiver() -> dict[str, Any]:
    path = REPO_ROOT / "specs" / "examples" / "waiver.json"
    loaded: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    return loaded


def _medium_waiver(**overrides: Any) -> dict[str, Any]:
    waiver = _golden_waiver()
    waiver.update(overrides)
    return waiver


def test_is_waivable_only_for_medium() -> None:
    assert is_waivable("medium") is True
    assert is_waivable("critical") is False
    assert is_waivable("high") is False
    assert is_waivable("low") is False


def test_agents_may_not_manage_waivers() -> None:
    assert may_manage_waiver({"type": "human", "id": "zarl3", "role": "security-reviewer"}) is True
    assert may_manage_waiver({"type": "agent", "id": "implementer", "role": "implementer"}) is False
    assert may_manage_waiver({"type": "ci", "id": "github-actions", "role": "reviewer"}) is False


def test_golden_waiver_is_valid_and_active() -> None:
    assert validate_waiver(_golden_waiver(), now=NOW) == []
    assert waiver_state(_golden_waiver(), now=NOW) == "active"
    assert check_waiver(_golden_waiver(), now=NOW).valid is True


def test_agent_created_waiver_is_rejected() -> None:
    waiver = _medium_waiver(created_by={"type": "agent", "id": "implementer", "role": "implementer"})
    assert REASON_AGENT_MAY_NOT_CREATE in validate_waiver(waiver, now=NOW)


def test_agent_approved_waiver_is_rejected() -> None:
    waiver = _medium_waiver(approved_by={"type": "agent", "id": "grill-security", "role": "security-reviewer"})
    assert REASON_AGENT_MAY_NOT_APPROVE in validate_waiver(waiver, now=NOW)


def test_approver_must_be_security_reviewer() -> None:
    waiver = _medium_waiver(approved_by={"type": "human", "id": "zarl3", "role": "implementer"})
    assert REASON_APPROVER_NOT_SECURITY_REVIEWER in validate_waiver(waiver, now=NOW)


def test_risk_owner_cannot_be_approver() -> None:
    waiver = _medium_waiver(owner={"type": "human", "id": "zarl3", "role": "security-reviewer"})
    assert REASON_APPROVER_IS_RISK_OWNER in validate_waiver(waiver, now=NOW)


def test_expiry_before_creation_is_rejected() -> None:
    waiver = _medium_waiver(expires_at="2026-09-01T00:00:00Z")
    assert REASON_EXPIRES_BEFORE_CREATED in validate_waiver(waiver, now=NOW)
    assert waiver_state(waiver, now=NOW) == "expired"


def test_revoked_waiver_state() -> None:
    assert waiver_state(_medium_waiver(status="revoked"), now=NOW) == "revoked"


def test_medium_without_waiver_is_blocked() -> None:
    decision = evaluate_risk("RISK-0003", "medium", [], now=NOW)
    assert decision.blocked is True
    assert REASON_WAIVER_MISSING in decision.reason_codes


def test_medium_with_active_waiver_is_not_blocked() -> None:
    decision = evaluate_risk("RISK-0003", "medium", [_golden_waiver()], now=NOW)
    assert decision.blocked is False
    assert decision.reason_codes == ()


def test_medium_waiver_for_another_risk_does_not_apply() -> None:
    decision = evaluate_risk("RISK-9999", "medium", [_golden_waiver()], now=NOW)
    assert decision.blocked is True
    assert REASON_WAIVER_MISSING in decision.reason_codes


def test_expired_waiver_reblocks_medium() -> None:
    waiver = _medium_waiver(expires_at="2026-09-01T00:00:00Z")
    decision = evaluate_risk("RISK-0003", "medium", [waiver], now=NOW)
    assert decision.blocked is True
    assert REASON_WAIVER_EXPIRED in decision.reason_codes


def test_revoked_waiver_reblocks_medium() -> None:
    decision = evaluate_risk("RISK-0003", "medium", [_medium_waiver(status="revoked")], now=NOW)
    assert decision.blocked is True
    assert REASON_WAIVER_REVOKED in decision.reason_codes


def test_agent_created_waiver_does_not_unblock_medium() -> None:
    waiver = _medium_waiver(created_by={"type": "agent", "id": "implementer", "role": "implementer"})
    decision = evaluate_risk("RISK-0003", "medium", [waiver], now=NOW)
    assert decision.blocked is True
    assert REASON_AGENT_MAY_NOT_CREATE in decision.reason_codes


def test_high_is_never_waived() -> None:
    decision = evaluate_risk("RISK-0003", "high", [_golden_waiver()], now=NOW)
    assert decision.blocked is True
    assert decision.reason_codes == (REASON_HIGH_NEVER_WAIVED,)


def test_critical_is_never_waived() -> None:
    decision = evaluate_risk("RISK-0003", "critical", [_golden_waiver()], now=NOW)
    assert decision.blocked is True
    assert decision.reason_codes == (REASON_CRITICAL_NEVER_WAIVED,)


def test_low_does_not_block() -> None:
    decision = evaluate_risk("RISK-0003", "low", [], now=NOW)
    assert decision.blocked is False
    assert decision.reason_codes == ()


def test_unknown_severity_blocks_fail_closed() -> None:
    decision = evaluate_risk("RISK-0003", "unknown", [], now=NOW)
    assert decision.blocked is True


def test_copy_of_golden_waiver_is_independent() -> None:
    waiver = deepcopy(_golden_waiver())
    waiver["approved_by"] = {"type": "human", "id": "reviewer-2", "role": "security-reviewer"}
    assert validate_waiver(waiver, now=NOW) == []


def test_cli_reports_active_waiver(tmp_path: Path) -> None:
    path = tmp_path / "waiver.json"
    path.write_text(json.dumps(_golden_waiver()), encoding="utf-8")
    assert main(["waiver", str(path), "--now", "2026-10-01T00:00:00Z"]) == 0


def test_cli_blocks_expired_waiver(tmp_path: Path) -> None:
    path = tmp_path / "waiver.json"
    path.write_text(json.dumps(_medium_waiver(expires_at="2026-09-01T00:00:00Z")), encoding="utf-8")
    assert main(["waiver", str(path), "--now", "2026-10-01T00:00:00Z"]) == 1