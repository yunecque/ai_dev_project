"""Evidence store, compression layer, and record builder (M1, TASK-0004)."""

from __future__ import annotations

from .compression import (
    DEFAULT_EXCERPT_BYTES,
    DEFAULT_MAX_BYTES,
    CompressionResult,
    compress_for_context,
)
from .pipeline import SensitiveContentError, ToolOutputResult, process_tool_output
from .record import build_evidence_record
from .store import EvidenceStore

__all__ = [
    "DEFAULT_EXCERPT_BYTES",
    "DEFAULT_MAX_BYTES",
    "CompressionResult",
    "EvidenceStore",
    "SensitiveContentError",
    "ToolOutputResult",
    "build_evidence_record",
    "compress_for_context",
    "process_tool_output",
]