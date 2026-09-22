"""Trust-tier model for inputs (ADR-0007).

Only ``trusted`` inputs may be treated as instructions. ``untrusted`` content is data,
and ``sensitive`` content must never enter the model context.
"""

from __future__ import annotations

from enum import Enum


class TrustTier(str, Enum):
    TRUSTED = "trusted"
    UNTRUSTED = "untrusted"
    SENSITIVE = "sensitive"


_TRUSTED_SOURCES = frozenset({"approved_artifact", "policy", "schema", "pinned_template"})
_SENSITIVE_SOURCES = frozenset({"secret", "credential", "pii", "production_config"})


def can_use_as_instruction(tier: TrustTier) -> bool:
    """Return True only for trusted inputs."""
    return tier is TrustTier.TRUSTED


def classify_source(source: str) -> TrustTier:
    """Map a source kind to a tier; unknown sources default to untrusted."""
    if source in _TRUSTED_SOURCES:
        return TrustTier.TRUSTED
    if source in _SENSITIVE_SOURCES:
        return TrustTier.SENSITIVE
    return TrustTier.UNTRUSTED