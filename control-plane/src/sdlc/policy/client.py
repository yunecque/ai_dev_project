"""OPA policy client for the ``pre-tool-call`` enforcement point (ADR-0004, fail-closed).

Any transport error, timeout, malformed response, or unexpected OPA result is treated as a
deny. The agent never receives an implicit allow.
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

REASON_ALLOWED = "ALLOWED"
REASON_DENIED = "DENIED"
REASON_POLICY_UNAVAILABLE = "POLICY_UNAVAILABLE"
REASON_POLICY_MALFORMED = "POLICY_MALFORMED"

DEFAULT_BASE_URL = "http://localhost:8181"
DEFAULT_TIMEOUT_SECONDS = 2.0


@dataclass(frozen=True)
class PolicyResult:
    """Normalized outcome of a policy evaluation."""

    allow: bool
    reason_codes: tuple[str, ...]
    policy_bundle_version: str
    input_digest: str


def compute_input_digest(payload: Mapping[str, Any]) -> str:
    """Return the sha256 of the canonical JSON encoding of ``payload``."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _decision_path(point: str) -> str:
    return f"v1/data/sdlc/{point.replace('-', '_')}/decision"


class PolicyClient:
    """Query OPA for a decision and fail closed on anything unexpected."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        bundle_version: str = "unknown",
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._bundle_version = bundle_version
        self._timeout = timeout

    def evaluate(self, *, point: str, payload: Mapping[str, Any]) -> PolicyResult:
        digest = compute_input_digest(payload)
        request = self._build_request(point, payload)
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                raw = response.read()
        except (urllib.error.URLError, OSError, TimeoutError):
            return self._fail_closed(REASON_POLICY_UNAVAILABLE, digest)
        return self._parse(raw, digest)

    def _build_request(self, point: str, payload: Mapping[str, Any]) -> urllib.request.Request:
        url = f"{self._base_url}/{_decision_path(point)}"
        body = json.dumps({"input": payload}).encode("utf-8")
        return urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

    def _parse(self, raw: bytes, digest: str) -> PolicyResult:
        try:
            body: Any = json.loads(raw)
        except json.JSONDecodeError:
            return self._fail_closed(REASON_POLICY_MALFORMED, digest)
        if not isinstance(body, dict) or "result" not in body:
            return self._fail_closed(REASON_POLICY_MALFORMED, digest)
        result: Any = body["result"]
        if isinstance(result, bool):
            reason = REASON_ALLOWED if result else REASON_DENIED
            return PolicyResult(result, (reason,), self._bundle_version, digest)
        if not isinstance(result, dict) or not isinstance(result.get("allow"), bool):
            return self._fail_closed(REASON_POLICY_MALFORMED, digest)
        allow: bool = result["allow"]
        codes: Any = result.get("reason_codes")
        if isinstance(codes, list) and codes and all(isinstance(code, str) for code in codes):
            reason_codes = tuple(codes)
        else:
            reason_codes = (REASON_ALLOWED if allow else REASON_DENIED,)
        return PolicyResult(allow, reason_codes, self._bundle_version, digest)

    def _fail_closed(self, reason: str, digest: str) -> PolicyResult:
        return PolicyResult(False, (reason,), self._bundle_version, digest)