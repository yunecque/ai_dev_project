"""LLM adapter interface and deterministic stub (M6, TASK-0002)."""

from __future__ import annotations

from .base import LLMAdapter, LLMError, LLMRequest, LLMResponse
from .stub import DEFAULT_MODEL, StubLLM

__all__ = [
    "DEFAULT_MODEL",
    "LLMAdapter",
    "LLMError",
    "LLMRequest",
    "LLMResponse",
    "StubLLM",
]