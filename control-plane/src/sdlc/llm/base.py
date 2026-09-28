"""LLM adapter interface (M6, TASK-0002).

The LLM is an untrusted component: its output is data, never instructions. Adapters receive a
trusted request (system prompt + context built from approved artifacts) and return raw text that
callers must parse and schema-validate. Sensitive content must never be placed in ``context``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol


class LLMError(RuntimeError):
    """Raised when the adapter cannot produce a response (fail-closed)."""


@dataclass(frozen=True)
class LLMRequest:
    """A single completion request; ``context`` must already exclude sensitive content."""

    role: str
    system_prompt: str
    context: Mapping[str, Any]


@dataclass(frozen=True)
class LLMResponse:
    """Raw, untrusted model output."""

    text: str
    model: str


class LLMAdapter(Protocol):
    """Structural interface for LLM providers (real or stub)."""

    def complete(self, request: LLMRequest) -> LLMResponse: ...