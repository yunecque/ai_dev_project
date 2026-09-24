"""Command line interface for the control plane (M0: artifacts)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .artifacts import find_repo_root, render_artifact, validate_artifact, validate_file
from .deploy_verify import CandidateError, load_candidate, verify_release
from .evidence import EvidenceStore
from .mcp import MCPServer
from .policy import PolicyClient
from .runner import RunnerExecutor, RunRegistry
from .tools import ArtifactStore, ToolRegistry, register_artifact_tools
from .traceability import format_report, trace_feature
from .waiver import check_waiver, parse_timestamp


def _rfc3339(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _cmd_validate(args: argparse.Namespace) -> int:
    repo_root = find_repo_root()
    failures = 0
    for raw in args.paths:
        path = Path(raw)
        if not path.is_file():
            print(f"SKIP {path}: not a file", file=sys.stderr)
            failures += 1
            continue
        errors = validate_file(path, repo_root)
        if errors:
            failures += 1
            print(f"INVALID {path}", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
        else:
            print(f"OK      {path}")
    return 1 if failures else 0


def _cmd_render(args: argparse.Namespace) -> int:
    path = Path(args.path)
    instance = json.loads(path.read_text(encoding="utf-8"))
    markdown = render_artifact(instance, source=path.name)
    if args.output:
        Path(args.output).write_text(markdown, encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        sys.stdout.write(markdown)
    return 0


def _cmd_waiver(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.is_file():
        print(f"SKIP {path}: not a file", file=sys.stderr)
        return 1
    instance = json.loads(path.read_text(encoding="utf-8"))
    schema_errors = validate_artifact(instance, find_repo_root())
    if schema_errors:
        print(f"INVALID {path}", file=sys.stderr)
        for error in schema_errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    now = parse_timestamp(args.now) if args.now else datetime.now(UTC)
    check = check_waiver(instance, now=now)
    if check.valid:
        print(f"OK      {path} (active)")
        return 0
    print(f"BLOCKED {path} state={check.state}", file=sys.stderr)
    for reason in check.reason_codes:
        print(f"  - {reason}", file=sys.stderr)
    return 1


def _cmd_deploy_verify(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.is_file():
        print(f"SKIP {path}: not a file", file=sys.stderr)
        return 1
    repo_root = find_repo_root()
    try:
        candidate = load_candidate(path, repo_root)
    except CandidateError as exc:
        print(f"INVALID {path}", file=sys.stderr)
        print(f"  - {exc}", file=sys.stderr)
        return 1
    now = parse_timestamp(args.now) if args.now else datetime.now(UTC)
    actor = {"type": "ci", "id": args.actor_id, "role": args.actor_role}
    policy = PolicyClient(base_url=args.opa_url, bundle_version=args.bundle_version)
    verification = verify_release(
        policy,
        candidate,
        bundle_id=args.bundle_id,
        decision_id=args.decision_id,
        created_at=_rfc3339(now),
        actor=actor,
        run_id=args.run_id,
        repo_root=repo_root,
    )
    if args.output_dir:
        output = Path(args.output_dir)
        output.mkdir(parents=True, exist_ok=True)
        (output / "evidence-bundle.json").write_text(
            json.dumps(verification.bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        (output / "policy-decision.json").write_text(
            json.dumps(verification.decision, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    if verification.allow:
        print(f"ALLOW   {path}")
        return 0
    print(f"DENY    {path}", file=sys.stderr)
    for reason in verification.reason_codes:
        print(f"  - {reason}", file=sys.stderr)
    return 1


def _cmd_trace(args: argparse.Namespace) -> int:
    repo_root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root()
    report = trace_feature(repo_root, args.feature)
    if args.as_json:
        print(json.dumps(asdict(report), indent=2, ensure_ascii=False))
    else:
        print(format_report(report))
    return 0 if report.complete else 1


def _cmd_mcp(args: argparse.Namespace) -> int:
    secret_hex = os.environ.get("SDLC_MCP_SECRET")
    if not secret_hex:
        print("SDLC_MCP_SECRET is required (hex-encoded capability secret)", file=sys.stderr)
        return 1
    try:
        secret = bytes.fromhex(secret_hex)
    except ValueError:
        print("SDLC_MCP_SECRET must be hex-encoded", file=sys.stderr)
        return 1
    capabilities = RunRegistry(secret=secret)
    run_id = os.environ.get("SDLC_RUN_ID")
    if run_id:
        actor_raw = os.environ.get(
            "SDLC_ACTOR_JSON", '{"type": "agent", "id": "opencode", "role": "implementer"}'
        )
        try:
            actor = json.loads(actor_raw)
        except json.JSONDecodeError:
            print("SDLC_ACTOR_JSON must be valid JSON", file=sys.stderr)
            return 1
        capabilities.start(actor, run_id=run_id)
    tools = ToolRegistry()
    register_artifact_tools(tools, ArtifactStore(Path(args.artifacts_dir)))
    executor = RunnerExecutor(
        policy=PolicyClient(base_url=args.opa_url),
        capabilities=capabilities,
        tools=tools,
        evidence_store=EvidenceStore(Path(args.evidence_dir)),
    )
    server = MCPServer(executor=executor, tools=tools)
    for line in sys.stdin:
        stripped = line.strip()
        if not stripped:
            continue
        sys.stdout.write(server.handle_line(stripped) + "\n")
        sys.stdout.flush()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sdlc", description="Secure Agentic SDLC control plane")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate workflow artifacts against JSON Schema")
    validate.add_argument("paths", nargs="+")
    validate.set_defaults(func=_cmd_validate)

    render = sub.add_parser("render", help="render an artifact JSON to Markdown")
    render.add_argument("path")
    render.add_argument("-o", "--output")
    render.set_defaults(func=_cmd_render)

    waiver = sub.add_parser("waiver", help="validate a waiver and report whether it is in force")
    waiver.add_argument("path")
    waiver.add_argument("--now", help="RFC3339 evaluation time (defaults to current time)")
    waiver.set_defaults(func=_cmd_waiver)

    deploy_verify = sub.add_parser(
        "deploy-verify", help="verify a release candidate against the pre-deployment policy"
    )
    deploy_verify.add_argument("path", help="release-candidate JSON")
    deploy_verify.add_argument("--opa-url", default="http://localhost:8181")
    deploy_verify.add_argument("--bundle-version", default="unknown")
    deploy_verify.add_argument("--run-id", default="RUN-deploy-verify")
    deploy_verify.add_argument("--now", help="RFC3339 evaluation time (defaults to current time)")
    deploy_verify.add_argument("--output-dir", help="directory for evidence-bundle/policy-decision")
    deploy_verify.add_argument("--bundle-id", default="EB-0001")
    deploy_verify.add_argument("--decision-id", default="PD-0001")
    deploy_verify.add_argument("--actor-id", default="deploy-verify")
    deploy_verify.add_argument("--actor-role", default="release-approver")
    deploy_verify.set_defaults(func=_cmd_deploy_verify)

    trace = sub.add_parser("trace", help="audit the artifact traceability chain for a feature")
    trace.add_argument("--feature", required=True, help="e.g. FEAT-0001")
    trace.add_argument("--repo-root", help="repository root (defaults to discovered root)")
    trace.add_argument("--json", action="store_true", dest="as_json")
    trace.set_defaults(func=_cmd_trace)

    mcp = sub.add_parser("mcp", help="serve allowlisted tools over a stdio MCP bridge")
    mcp.add_argument("--opa-url", default="http://localhost:8181")
    mcp.add_argument("--artifacts-dir", default="specs/artifacts")
    mcp.add_argument("--evidence-dir", default="specs/evidence")
    mcp.set_defaults(func=_cmd_mcp)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
