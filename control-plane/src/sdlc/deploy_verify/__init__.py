"""Independent pre-deployment release verification (M3, TASK-0002)."""

from __future__ import annotations

from .bundle import BUNDLE_TYPE, build_evidence_bundle, bundle_digest
from .candidate import (
    CANDIDATE_SCHEMA,
    CANDIDATE_TYPE,
    CandidateError,
    canonical_json,
    load_candidate,
    sha256_digest,
    validate_candidate,
)
from .verify import ReleaseVerification, verify_release

__all__ = [
    "BUNDLE_TYPE",
    "CANDIDATE_SCHEMA",
    "CANDIDATE_TYPE",
    "CandidateError",
    "ReleaseVerification",
    "build_evidence_bundle",
    "bundle_digest",
    "canonical_json",
    "load_candidate",
    "sha256_digest",
    "validate_candidate",
    "verify_release",
]
