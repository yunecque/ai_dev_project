package sdlc.artifact_transition

human_author := {"type": "human", "id": "zarl3", "role": "author"}

agent_actor := {"type": "agent", "id": "implementer", "role": "implementer"}

test_allows_specification_draft_to_in_review if {
	payload := {
		"artifact_type": "specification",
		"from_status": "draft",
		"to_status": "in_review",
		"actor": agent_actor,
	}
	decision.allow with input as payload
}

test_allows_specification_in_review_to_approved if {
	result := decision with input as {
		"artifact_type": "specification",
		"from_status": "in_review",
		"to_status": "approved",
		"actor": human_author,
	}
	result.allow == true
}

test_denies_illegal_transition if {
	result := decision with input as {
		"artifact_type": "specification",
		"from_status": "draft",
		"to_status": "approved",
		"actor": human_author,
	}
	result.allow == false
	result.reason_codes[_] == "ILLEGAL_TRANSITION"
}

test_denies_unknown_artifact_type if {
	result := decision with input as {
		"artifact_type": "mystery",
		"from_status": "draft",
		"to_status": "approved",
		"actor": human_author,
	}
	result.allow == false
	result.reason_codes == ["UNKNOWN_ARTIFACT_TYPE"]
}

test_denies_unknown_status if {
	result := decision with input as {
		"artifact_type": "specification",
		"from_status": "bogus",
		"to_status": "approved",
		"actor": human_author,
	}
	result.allow == false
	result.reason_codes[_] == "UNKNOWN_STATUS"
}

test_denies_agent_approval if {
	result := decision with input as {
		"artifact_type": "specification",
		"from_status": "in_review",
		"to_status": "approved",
		"actor": agent_actor,
	}
	result.allow == false
	result.reason_codes[_] == "AGENT_MAY_NOT_APPROVE"
}

test_allows_task_todo_to_in_progress if {
	decision.allow with input as {
		"artifact_type": "task",
		"from_status": "todo",
		"to_status": "in_progress",
		"actor": agent_actor,
	}
}

test_denies_task_done_from_todo if {
	result := decision with input as {
		"artifact_type": "task",
		"from_status": "todo",
		"to_status": "done",
		"actor": {"type": "human", "id": "zarl3", "role": "reviewer"},
	}
	result.allow == false
	result.reason_codes[_] == "ILLEGAL_TRANSITION"
}

test_allows_waiver_active_to_revoked if {
	payload := {
		"artifact_type": "waiver",
		"from_status": "active",
		"to_status": "revoked",
		"actor": {"type": "human", "id": "zarl3", "role": "security-reviewer"},
	}
	decision.allow with input as payload
}

test_denies_critical_finding if {
	result := decision with input as {
		"artifact_type": "task",
		"from_status": "in_review",
		"to_status": "done",
		"actor": {"type": "human", "id": "zarl3", "role": "reviewer"},
		"now": "2026-10-01T00:00:00Z",
		"findings": [{"risk_id": "RISK-0001", "severity": "critical"}],
	}
	result.allow == false
	result.reason_codes[_] == "BLOCKING_FINDING"
}

test_denies_high_finding if {
	result := decision with input as {
		"artifact_type": "task",
		"from_status": "in_review",
		"to_status": "done",
		"actor": {"type": "human", "id": "zarl3", "role": "reviewer"},
		"now": "2026-10-01T00:00:00Z",
		"findings": [{"risk_id": "RISK-0001", "severity": "high"}],
	}
	result.allow == false
	result.reason_codes[_] == "BLOCKING_FINDING"
}

test_denies_medium_without_waiver if {
	result := decision with input as {
		"artifact_type": "task",
		"from_status": "in_review",
		"to_status": "done",
		"actor": {"type": "human", "id": "zarl3", "role": "reviewer"},
		"now": "2026-10-01T00:00:00Z",
		"findings": [{"risk_id": "RISK-0003", "severity": "medium"}],
	}
	result.allow == false
	result.reason_codes[_] == "UNRESOLVED_MEDIUM"
}

test_allows_medium_with_active_waiver if {
	result := decision with input as {
		"artifact_type": "task",
		"from_status": "in_review",
		"to_status": "done",
		"actor": {"type": "human", "id": "zarl3", "role": "reviewer"},
		"now": "2026-10-01T00:00:00Z",
		"findings": [{"risk_id": "RISK-0003", "severity": "medium"}],
		"waivers": [{
			"risk_id": "RISK-0003",
			"severity": "medium",
			"status": "active",
			"expires_at": "2026-12-21T00:00:00Z",
		}],
	}
	result.allow == true
}

test_denies_medium_with_expired_waiver if {
	result := decision with input as {
		"artifact_type": "task",
		"from_status": "in_review",
		"to_status": "done",
		"actor": {"type": "human", "id": "zarl3", "role": "reviewer"},
		"now": "2026-10-01T00:00:00Z",
		"findings": [{"risk_id": "RISK-0003", "severity": "medium"}],
		"waivers": [{
			"risk_id": "RISK-0003",
			"severity": "medium",
			"status": "active",
			"expires_at": "2026-09-01T00:00:00Z",
		}],
	}
	result.allow == false
	result.reason_codes[_] == "UNRESOLVED_MEDIUM"
}

test_allows_low_finding_without_waiver if {
	result := decision with input as {
		"artifact_type": "task",
		"from_status": "in_review",
		"to_status": "done",
		"actor": {"type": "human", "id": "zarl3", "role": "reviewer"},
		"now": "2026-10-01T00:00:00Z",
		"findings": [{"risk_id": "RISK-0004", "severity": "low"}],
	}
	result.allow == true
}

test_fails_closed_without_now_for_medium if {
	result := decision with input as {
		"artifact_type": "task",
		"from_status": "in_review",
		"to_status": "done",
		"actor": {"type": "human", "id": "zarl3", "role": "reviewer"},
		"findings": [{"risk_id": "RISK-0003", "severity": "medium"}],
		"waivers": [{
			"risk_id": "RISK-0003",
			"severity": "medium",
			"status": "active",
			"expires_at": "2026-12-21T00:00:00Z",
		}],
	}
	result.allow == false
	result.reason_codes[_] == "UNRESOLVED_MEDIUM"
}
