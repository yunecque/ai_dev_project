"""Deterministic stub LLM for tests and offline runs (M6, TASK-0002)."""

from __future__ import annotations

from collections.abc import Mapping

from .base import LLMError, LLMRequest, LLMResponse

DEFAULT_MODEL = "stub"


class StubLLM:
    """Return canned responses keyed by role; unknown roles fail closed."""

    def __init__(self, responses: Mapping[str, str], model: str = DEFAULT_MODEL) -> None:
        self._responses = dict(responses)
        self._model = model

    def complete(self, request: LLMRequest) -> LLMResponse:
        try:
            text = self._responses[request.role]
        except KeyError as exc:
            raise LLMError(f"no stub response for role {request.role!r}") from exc
        return LLMResponse(text=text, model=self._model)