// OPA guard plugin for the Secure Agentic SDLC platform (ADR-0011/0014).
//
// The platform is the single door: every direct tool call is checked against the OPA
// `pre-tool-call` policy and denied fail-closed when OPA is unavailable or denies. MCP tools
// (`sdlc_*`) are mediated by the platform server itself and are skipped here.

import type { Plugin } from "@opencode-ai/plugin"

const OPA_URL = process.env.OPA_URL ?? "http://localhost:8181"
const DENY_FALLBACK = ["POLICY_UNAVAILABLE"]

type Decision = { allow: boolean; reason_codes: string[] }

// Map opencode native tool names to the policy's tool vocabulary.
// Only names that already exist in `allowed_tools` are mapped; everything
// else falls through and stays denied (fail-closed).
function toPolicyTool(tool: string, args: Record<string, unknown>): string {
  switch (tool) {
    case "read":
      return "read_file"
    case "write":
    case "edit":
      return "write_file"
    case "glob":
    case "grep":
      return "list_files"
    case "skill":
      return `skill.${String(args.name ?? "")}`
    default:
      return tool
  }
}

async function decide(tool: string, path: string): Promise<Decision> {
  try {
    const response = await fetch(`${OPA_URL}/v1/data/sdlc/pre_tool_call/decision`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input: { tool, path, scope: "workspace" } }),
    })
    if (!response.ok) {
      return { allow: false, reason_codes: DENY_FALLBACK }
    }
    const body = (await response.json()) as { result?: unknown }
    const result = body.result as Decision | undefined
    if (!result || typeof result.allow !== "boolean") {
      return { allow: false, reason_codes: ["POLICY_MALFORMED"] }
    }
    return result
  } catch {
    return { allow: false, reason_codes: DENY_FALLBACK }
  }
}

export default (async () => {
  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool.startsWith("sdlc")) {
        return
      }
      const args = output.args as Record<string, unknown>
      // Normalize Windows separators to POSIX before the policy check. The policy's
      // slash-based markers ("secrets/", "credentials/") otherwise never match on
      // Windows paths (they contain "secrets\\"), silently disabling those two guards.
      // Keep this in sync if markers in policies/pre_tool_call.rego change.
      const path = String(args.filePath ?? args.path ?? args.file ?? "").replace(/\\/g, "/")
      const decision = await decide(toPolicyTool(input.tool, args), path)
      if (!decision.allow) {
        throw new Error(`OPA denied tool ${input.tool}: ${decision.reason_codes.join(",")}`)
      }
    },
    "permission.ask": async (input, output) => {
      const args = (input as Record<string, unknown>).args as Record<string, unknown> | undefined
      const decision = await decide(toPolicyTool(input.type, args ?? {}), String(input.pattern ?? ""))
      if (!decision.allow) {
        output.status = "deny"
      }
    },
  }
}) satisfies Plugin