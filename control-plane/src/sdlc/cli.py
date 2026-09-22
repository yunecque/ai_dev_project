"""Command line interface for the control plane (M0: artifacts)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .artifacts import find_repo_root, render_artifact, validate_file


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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
