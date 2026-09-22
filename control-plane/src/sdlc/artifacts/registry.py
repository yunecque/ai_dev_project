"""JSON Schema registry and artifact validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT202012

SCHEMA_DIR_REL = Path("contracts") / "schemas"
SCHEMA_SUFFIX = ".schema.json"


def find_repo_root(start: Path | None = None) -> Path:
    """Locate the repository root by the presence of contracts/schemas/common.schema.json."""
    origin = (start or Path(__file__)).resolve()
    for parent in [origin, *origin.parents]:
        if (parent / SCHEMA_DIR_REL / "common.schema.json").is_file():
            return parent
    raise FileNotFoundError("could not locate repository root (contracts/schemas/common.schema.json)")


def schema_dir(repo_root: Path | None = None) -> Path:
    return (repo_root or find_repo_root()) / SCHEMA_DIR_REL


def load_schema(name: str, repo_root: Path | None = None) -> dict[str, Any]:
    path = schema_dir(repo_root) / name
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def build_registry(repo_root: Path | None = None) -> Registry:
    """Register every schema by its $id and by its file name for relative $ref resolution."""
    directory = schema_dir(repo_root)
    resources: list[tuple[str, Resource]] = []
    for path in sorted(directory.glob(f"*{SCHEMA_SUFFIX}")):
        contents = json.loads(path.read_text(encoding="utf-8"))
        resource = Resource.from_contents(contents, default_specification=DRAFT202012)
        resources.append((contents.get("$id", path.name), resource))
        resources.append((path.name, resource))
    return Registry().with_resources(resources)


def artifact_schema_name(instance: dict[str, Any]) -> str:
    artifact_type = instance.get("artifact_type")
    if not isinstance(artifact_type, str) or not artifact_type:
        raise ValueError("artifact is missing a string 'artifact_type' field")
    return f"{artifact_type}{SCHEMA_SUFFIX}"


def validate_document(
    instance: dict[str, Any], schema_name: str, repo_root: Path | None = None
) -> list[str]:
    """Validate against an explicitly named schema; return human-readable errors."""
    schema = load_schema(schema_name, repo_root)
    validator = Draft202012Validator(schema, registry=build_registry(repo_root))
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    return [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errors]


def validate_artifact(instance: dict[str, Any], repo_root: Path | None = None) -> list[str]:
    """Return a list of human-readable validation errors (empty when valid)."""
    return validate_document(instance, artifact_schema_name(instance), repo_root)


def validate_file(path: Path, repo_root: Path | None = None) -> list[str]:
    instance: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(instance, dict):
        return [f"{path}: top-level JSON value must be an object"]
    if "artifact_type" not in instance and "baseline_id" in instance:
        return validate_document(instance, "baseline.schema.json", repo_root)
    return validate_artifact(instance, repo_root)
