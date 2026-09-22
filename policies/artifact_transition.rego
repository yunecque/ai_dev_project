package sdlc.artifact_transition

# Artifact lifecycle transition gate (ADR-0004, M2 TASK-0005).
#
# Query path: /v1/data/sdlc/artifact_transition/decision
# Input:
#   {
#     "artifact_type": string,
#     "from_status": string,
#     "to_status": string,
#     "actor": {"type": "human|agent|ci", "id": string, "role": string},
#     "now": RFC3339 string,                  # required when findings/waivers present
#     "findings": [{"risk_id": string, "severity": "critical|high|medium|low"}],
#     "waivers":  [{"risk_id": string, "severity": "medium", "status": "active",
#                   "expires_at": RFC3339 string}]
#   }
# Output: {"allow": bool, "reason_codes": [string]}
#
# Fail-closed: unknown artifact/status, illegal transition, agent approval, a
# critical/high finding, or an unwaived medium finding all deny.

approval_statuses := {"approved", "done"}

blocking_severities := {"critical", "high"}

statuses := {
	"specification": {"draft", "in_review", "approved", "rejected", "superseded"},
	"threat-model": {"draft", "in_review", "approved", "rejected", "superseded"},
	"plan": {"draft", "approved", "superseded"},
	"task": {"todo", "in_progress", "implemented", "in_review", "done", "blocked"},
	"waiver": {"active", "expired", "revoked"},
}

lifecycles := {
	"specification": {
		"draft": {"in_review", "superseded"},
		"in_review": {"approved", "rejected"},
		"approved": {"superseded"},
		"rejected": {"draft", "superseded"},
	},
	"threat-model": {
		"draft": {"in_review", "superseded"},
		"in_review": {"approved", "rejected"},
		"approved": {"superseded"},
		"rejected": {"draft", "superseded"},
	},
	"plan": {
		"draft": {"approved", "superseded"},
		"approved": {"superseded"},
	},
	"task": {
		"todo": {"in_progress", "blocked"},
		"in_progress": {"implemented", "blocked"},
		"implemented": {"in_review", "blocked"},
		"in_review": {"done", "implemented", "blocked"},
		"blocked": {"todo", "in_progress"},
		"done": set(),
	},
	"waiver": {
		"active": {"expired", "revoked"},
		"expired": set(),
		"revoked": set(),
	},
}

findings := object.get(input, "findings", [])

waivers := object.get(input, "waivers", [])

deny_reasons contains "UNKNOWN_ARTIFACT_TYPE" if {
	not lifecycles[input.artifact_type]
}

deny_reasons contains "UNKNOWN_STATUS" if {
	lifecycles[input.artifact_type]
	not statuses[input.artifact_type][input.from_status]
}

deny_reasons contains "UNKNOWN_STATUS" if {
	lifecycles[input.artifact_type]
	not statuses[input.artifact_type][input.to_status]
}

deny_reasons contains "ILLEGAL_TRANSITION" if {
	some from_status, targets in lifecycles[input.artifact_type]
	from_status == input.from_status
	not targets[input.to_status]
}

deny_reasons contains "AGENT_MAY_NOT_APPROVE" if {
	input.actor.type == "agent"
	approval_statuses[input.to_status]
}

deny_reasons contains "BLOCKING_FINDING" if {
	some finding in findings
	blocking_severities[finding.severity]
}

deny_reasons contains "UNRESOLVED_MEDIUM" if {
	some finding in findings
	finding.severity == "medium"
	not medium_is_waived(finding.risk_id)
}

medium_is_waived(risk_id) if {
	some waiver in waivers
	waiver.risk_id == risk_id
	waiver.severity == "medium"
	waiver.status == "active"
	waiver_is_unexpired(waiver)
}

waiver_is_unexpired(waiver) if {
	now := time.parse_rfc3339_ns(input.now)
	expires := time.parse_rfc3339_ns(waiver.expires_at)
	now < expires
}

decision := {"allow": false, "reason_codes": reason_list} if {
	count(deny_reasons) > 0
	reason_list := sort([reason | some reason in deny_reasons])
}

decision := {"allow": true, "reason_codes": ["ALLOWED"]} if {
	count(deny_reasons) == 0
}
