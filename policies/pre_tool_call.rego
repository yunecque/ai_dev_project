package sdlc.pre_tool_call

# First pre-tool-call policy (ADR-0004, fail-closed enforcement).
#
# Query path: /v1/data/sdlc/pre_tool_call/decision
# Input: {"tool": string, "path": string, "scope": string, "actor": {...}}
# Output: {"allow": bool, "reason_codes": [string]}

allowed_tools := {
	"read_file", "write_file", "list_files", "run_tests",
	"read_artifact", "write_artifact", "list_artifacts", "open_pr",
	"skill.grill", "skill.grill-security", "skill.planner", "skill.task-writer", "skill.reviewer",
}

sensitive_markers := [".env", "secrets/", "credentials/", ".pem", ".key", "id_rsa", "id_ed25519"]

# Protected zones (AGENTS.md). Direct file writes here are denied; the sanctioned
# path for specs/ artifacts is `write_artifact` (canonical JSON), which is NOT gated
# by protected_paths — only direct `write_file` is. Keep in sync with AGENTS.md.
protected_paths := [
	".github/", "contracts/", "policies/", "security/", "infra/", "specs/", ".opencode/",
	"docs/adr/", "docs/roadmap.md", "baseline.json", "ARCHITECTURE_BASELINE.md",
]

deny_reasons contains "TOOL_NOT_IN_ALLOWLIST" if {
	not allowed_tools[input.tool]
}

deny_reasons contains "SENSITIVE_PATH" if {
	some marker in sensitive_markers
	contains(input.path, marker)
}

# Only `write_file` is restricted here; `write_artifact` legitimately writes specs/.
deny_reasons contains "PROTECTED_PATH" if {
	input.tool == "write_file"
	some path in protected_paths
	contains(input.path, path)
}

decision := {"allow": false, "reason_codes": reason_list} if {
	count(deny_reasons) > 0
	reason_list := sort([reason | some reason in deny_reasons])
}

decision := {"allow": true, "reason_codes": ["ALLOWED"]} if {
	count(deny_reasons) == 0
}
