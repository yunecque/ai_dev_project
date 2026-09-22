"""Scoped, HMAC-signed capability tokens for the ephemeral run registry (ADR-0011).

Tokens are compact ``v1.<payload>.<signature>`` strings. Payload is base64url-encoded canonical
JSON ``{run_id, tool, scope, exp}``. Verification is fail-closed: malformed, tampered, expired,
mismatched, unknown, or revoked capabilities are rejected.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any

TOKEN_VERSION = "v1"

CAPABILITY_VALID = "CAPABILITY_VALID"
REASON_MALFORMED_TOKEN = "MALFORMED_TOKEN"
REASON_SIGNATURE_INVALID = "SIGNATURE_INVALID"
REASON_RUN_UNKNOWN = "RUN_UNKNOWN"
REASON_RUN_FINISHED = "RUN_FINISHED"
REASON_CAPABILITY_EXPIRED = "CAPABILITY_EXPIRED"
REASON_TOOL_MISMATCH = "TOOL_NOT_ALLOWED"
REASON_SCOPE_MISMATCH = "SCOPE_MISMATCH"


@dataclass(frozen=True)
class Capability:
    """The claims carried by a signed capability token."""

    run_id: str
    tool: str
    scope: str
    expires_at: int


@dataclass(frozen=True)
class CapabilityCheck:
    """Outcome of verifying a capability token against a requested tool and scope."""

    valid: bool
    reason: str
    run_id: str | None = None
    tool: str | None = None
    scope: str | None = None


@dataclass(frozen=True)
class DecodeResult:
    """Result of decoding a token: either a capability or a failure reason code."""

    capability: Capability | None
    error: str | None


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _sign(secret: bytes, signing_input: str) -> str:
    digest = hmac.new(secret, signing_input.encode("ascii"), hashlib.sha256).digest()
    return _b64encode(digest)


def issue_token(secret: bytes, capability: Capability) -> str:
    """Return a signed token encoding ``capability``."""
    payload = {
        "run_id": capability.run_id,
        "tool": capability.tool,
        "scope": capability.scope,
        "exp": capability.expires_at,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    encoded = _b64encode(raw)
    signing_input = f"{TOKEN_VERSION}.{encoded}"
    return f"{signing_input}.{_sign(secret, signing_input)}"


def decode_token(secret: bytes, token: str) -> DecodeResult:
    """Verify the signature and decode the payload; never raises."""
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != TOKEN_VERSION or not parts[1] or not parts[2]:
        return DecodeResult(None, REASON_MALFORMED_TOKEN)
    _version, encoded, signature = parts
    signing_input = f"{TOKEN_VERSION}.{encoded}"
    if not hmac.compare_digest(_sign(secret, signing_input), signature):
        return DecodeResult(None, REASON_SIGNATURE_INVALID)
    try:
        decoded: Any = json.loads(_b64decode(encoded))
    except (ValueError, json.JSONDecodeError):
        return DecodeResult(None, REASON_MALFORMED_TOKEN)
    if not isinstance(decoded, dict):
        return DecodeResult(None, REASON_MALFORMED_TOKEN)
    run_id = decoded.get("run_id")
    tool = decoded.get("tool")
    scope = decoded.get("scope")
    exp = decoded.get("exp")
    if not (
        isinstance(run_id, str)
        and isinstance(tool, str)
        and isinstance(scope, str)
        and isinstance(exp, int)
        and not isinstance(exp, bool)
    ):
        return DecodeResult(None, REASON_MALFORMED_TOKEN)
    return DecodeResult(Capability(run_id=run_id, tool=tool, scope=scope, expires_at=exp), None)