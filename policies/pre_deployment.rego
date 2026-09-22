package sdlc.pre_deployment

# Independent pre-deployment release gate (ADR-0004/0005, M3 TASK-0001).
#
# Query path: /v1/data/sdlc/pre_deployment/decision
# Input:
#   {
#     "image": string,
#     "signature":  {"verified": bool, "issuer": string, "identity": string},
#     "sbom":       {"present": bool, "digest": string},
#     "provenance": {"verified": bool, "builder": string},
#     "policy_decisions": [{"point": string, "decision": "allow"|"deny"}],
#     "required_approver_role": string,
#     "approvals": [{"role": string, "actor": {"type": string, "id": string, "role": string}}]
#   }
# Output: {"allow": bool, "reason_codes": [string]}
#
# Fail-closed: a missing/unverified signature, SBOM, provenance, policy decision, or a
# missing independent (human) approval denies the release. Agent approvals never count.

required_points := {"artifact-transition", "pr-ci"}

signature := object.get(input, "signature", {})

sbom := object.get(input, "sbom", {})

provenance := object.get(input, "provenance", {})

policy_decisions := object.get(input, "policy_decisions", [])

approvals := object.get(input, "approvals", [])

deny_reasons contains "MISSING_IMAGE" if {
	object.get(input, "image", "") == ""
}

deny_reasons contains "MISSING_SIGNATURE" if {
	not signature.verified
}

deny_reasons contains "MISSING_SBOM" if {
	not sbom.present
}

deny_reasons contains "MISSING_PROVENANCE" if {
	not provenance.verified
}

deny_reasons contains "MISSING_POLICY_DECISION" if {
	some point in required_points
	not point_allowed(point)
}

deny_reasons contains "MISSING_APPROVAL" if {
	not approval_present
}

deny_reasons contains "AGENT_MAY_NOT_APPROVE" if {
	some approval in approvals
	approval.actor.type == "agent"
}

point_allowed(point) if {
	some decision in policy_decisions
	decision.point == point
	decision.decision == "allow"
}

approval_present if {
	some approval in approvals
	approval.role == input.required_approver_role
	approval.actor.type == "human"
}

decision := {"allow": false, "reason_codes": reason_list} if {
	count(deny_reasons) > 0
	reason_list := sort([reason | some reason in deny_reasons])
}

decision := {"allow": true, "reason_codes": ["ALLOWED"]} if {
	count(deny_reasons) == 0
}
