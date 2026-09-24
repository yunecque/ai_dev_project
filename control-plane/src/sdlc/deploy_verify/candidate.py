"""Load and validate a release candidate for the pre-deployment gate (M3, TASK-0002).

The candidate is untrusted input produced by CI: it is schema-validated and never treated as an
instruction. Its canonical SHA-256 digest anchors the evidence bundle.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..artifacts import validate_document

CANDIDATE_SCHEMA = "release-candidate.schema.json"
CANDIDATE_TYPE = "release-candidate"


class CandidateError(ValueError):
    """Raised when a release candidate is malformed or fails schema validation."""


def canonical_json(data: Mapping[str, Any]) -> str:
    """Return the canonical JSON encoding used for content addressing."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_digest(data: Mapping[str, Any]) -> str:
    """Return the SHA-256 of the canonical JSON encoding of ``data``."""
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


def validate_candidate(instance: Mapping[str, Any], repo_root: Path | None = None) -> None:
    """Validate ``instance`` against the release-candidate schema or raise ``CandidateError``."""
    if not isinstance(instance, Mapping):
        raise CandidateError("release candidate must be a JSON object")
    errors = validate_document(dict(instance), CANDIDATE_SCHEMA, repo_root)
    if errors:
        raise CandidateError("; ".join(errors))


def load_candidate(path: Path, repo_root: Path | None = None) -> dict[str, Any]:
    """Read, parse, and validate a release candidate from ``path``."""
    try:
        instance: Any = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CandidateError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(instance, dict):
        raise CandidateError(f"{path}: top-level JSON value must be an object")
    validate_candidate(instance, repo_root)
    return instance
