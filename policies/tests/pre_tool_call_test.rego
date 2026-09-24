package sdlc.pre_tool_call

test_allows_allowlisted_tool_on_safe_path if {
	decision.allow with input as {"tool": "read_file", "path": "src/main.go", "scope": "workspace"}
}

test_denies_unknown_tool if {
	result := decision with input as {"tool": "shell_exec", "path": "src/main.go", "scope": "workspace"}
	result.allow == false
	result.reason_codes[_] == "TOOL_NOT_IN_ALLOWLIST"
}

test_denies_dotenv_read if {
	result := decision with input as {"tool": "read_file", "path": ".env", "scope": "workspace"}
	result.allow == false
	result.reason_codes[_] == "SENSITIVE_PATH"
}

test_denies_secrets_directory if {
	result := decision with input as {"tool": "read_file", "path": "secrets/db.txt", "scope": "workspace"}
	result.allow == false
	result.reason_codes[_] == "SENSITIVE_PATH"
}

test_denies_private_key if {
	result := decision with input as {"tool": "write_file", "path": "certs/server.key", "scope": "workspace"}
	result.allow == false
	result.reason_codes[_] == "SENSITIVE_PATH"
}

test_denies_unknown_tool_and_sensitive_path_together if {
	result := decision with input as {"tool": "shell_exec", "path": ".env", "scope": "workspace"}
	result.allow == false
	count(result.reason_codes) == 2
}

test_allows_write_to_safe_path if {
	decision.allow with input as {"tool": "write_file", "path": "apps/gateway/server.go", "scope": "workspace"}
}

test_allows_artifact_writer if {
	decision.allow with input as {"tool": "write_artifact", "path": "specs/tasks/TASK-0001.json", "scope": "workspace"}
}

test_allows_task_writer_skill if {
	decision.allow with input as {"tool": "skill.task-writer", "path": "", "scope": "skills"}
}

test_denies_unknown_skill if {
	result := decision with input as {"tool": "skill.rogue", "path": "", "scope": "skills"}
	result.allow == false
	result.reason_codes[_] == "TOOL_NOT_IN_ALLOWLIST"
}
