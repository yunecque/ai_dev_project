package sdlc.pre_deployment

valid_input := {
	"image": "ghcr.io/yunecque/ai_dev_project/domain:abc123",
	"signature": {
		"verified": true,
		"issuer": "https://token.actions.githubusercontent.com",
		"identity": "repo:yunecque/ai_dev_project",
	},
	"sbom": {"present": true, "digest": "abc123"},
	"provenance": {"verified": true, "builder": "github-actions"},
	"policy_decisions": [
		{"point": "artifact-transition", "decision": "allow"},
		{"point": "pr-ci", "decision": "allow"},
	],
	"required_approver_role": "release-approver",
	"approvals": [{
		"role": "release-approver",
		"actor": {"type": "human", "id": "zarl3", "role": "release-approver"},
	}],
}

test_allows_complete_release if {
	decision.allow with input as valid_input
}

test_denies_missing_image if {
	result := decision with input as object.union(valid_input, {"image": ""})
	result.allow == false
	result.reason_codes[_] == "MISSING_IMAGE"
}

test_denies_unverified_signature if {
	result := decision with input as object.union(valid_input, {"signature": {"verified": false}})
	result.allow == false
	result.reason_codes[_] == "MISSING_SIGNATURE"
}

test_denies_missing_sbom if {
	result := decision with input as object.union(valid_input, {"sbom": {"present": false}})
	result.allow == false
	result.reason_codes[_] == "MISSING_SBOM"
}

test_denies_missing_provenance if {
	result := decision with input as object.union(valid_input, {"provenance": {"verified": false}})
	result.allow == false
	result.reason_codes[_] == "MISSING_PROVENANCE"
}

test_denies_missing_policy_decision if {
	payload := object.union(valid_input, {"policy_decisions": [{"point": "artifact-transition", "decision": "allow"}]})
	result := decision with input as payload
	result.allow == false
	result.reason_codes[_] == "MISSING_POLICY_DECISION"
}

test_denies_denied_policy_decision if {
	payload := object.union(valid_input, {
		"policy_decisions": [
			{"point": "artifact-transition", "decision": "allow"},
			{"point": "pr-ci", "decision": "deny"},
		],
	})
	result := decision with input as payload
	result.allow == false
	result.reason_codes[_] == "MISSING_POLICY_DECISION"
}

test_denies_missing_approval if {
	result := decision with input as object.union(valid_input, {"approvals": []})
	result.allow == false
	result.reason_codes[_] == "MISSING_APPROVAL"
}

test_denies_agent_approval if {
	payload := object.union(valid_input, {
		"approvals": [{
			"role": "release-approver",
			"actor": {"type": "agent", "id": "implementer", "role": "implementer"},
		}],
	})
	result := decision with input as payload
	result.allow == false
	result.reason_codes[_] == "AGENT_MAY_NOT_APPROVE"
}

test_denies_wrong_approver_role if {
	payload := object.union(valid_input, {
		"approvals": [{
			"role": "reviewer",
			"actor": {"type": "human", "id": "zarl3", "role": "reviewer"},
		}],
	})
	result := decision with input as payload
	result.allow == false
	result.reason_codes[_] == "MISSING_APPROVAL"
}

test_denies_when_required_role_absent if {
	payload := object.remove(valid_input, ["required_approver_role"])
	result := decision with input as payload
	result.allow == false
	result.reason_codes[_] == "MISSING_APPROVAL"
}

test_empty_input_is_denied if {
	result := decision with input as {}
	result.allow == false
}
