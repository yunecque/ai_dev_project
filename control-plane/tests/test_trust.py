"""Tests for the trust-tier model (ADR-0007).

Only ``trusted`` inputs may be treated as instructions; everything else is data.
"""

from __future__ import annotations

import pytest

from sdlc.trust import TrustTier, can_use_as_instruction, classify_source


def test_tier_values_match_schema() -> None:
    assert {tier.value for tier in TrustTier} == {"trusted", "untrusted", "sensitive"}


def test_only_trusted_may_be_instruction() -> None:
    assert can_use_as_instruction(TrustTier.TRUSTED) is True
    assert can_use_as_instruction(TrustTier.UNTRUSTED) is False
    assert can_use_as_instruction(TrustTier.SENSITIVE) is False


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("approved_artifact", TrustTier.TRUSTED),
        ("policy", TrustTier.TRUSTED),
        ("issue", TrustTier.UNTRUSTED),
        ("tool_output", TrustTier.UNTRUSTED),
        ("llm_output", TrustTier.UNTRUSTED),
        ("secret", TrustTier.SENSITIVE),
        ("credential", TrustTier.SENSITIVE),
        ("pii", TrustTier.SENSITIVE),
    ],
)
def test_classify_source(source: str, expected: TrustTier) -> None:
    assert classify_source(source) is expected


def test_unknown_source_is_untrusted() -> None:
    assert classify_source("something-else") is TrustTier.UNTRUSTED