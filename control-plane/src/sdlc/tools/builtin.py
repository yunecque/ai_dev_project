"""Built-in artifact tools backed by a content store (M6, TASK-0005/0006).

These are the safe, allowlisted primitives the agent may call: read/list/write canonical workflow
artifacts. ``write_artifact`` validates the document against its JSON Schema before persisting, so
an invalid artifact can never enter the store through the tool surface.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..artifacts import validate_artifact
from .registry import ToolHandler, ToolRegistry, ToolSpec

READ_SCHEMA = {
    "type": "object",
    "required": ["artifact_id"],
    "properties": {"artifact_id": {"type": "string"}},
    "additionalProperties": False,
}
READ_RESULT = {
    "type": "object",
    "required": ["artifact_id", "document"],
    "properties": {
        "artifact_id": {"type": "string"},
        "document": {"type": "object"},
    },
}
WRITE_SCHEMA = {
    "type": "object",
    "required": ["document"],
    "properties": {"document": {"type": "object"}},
    "additionalProperties": False,
}
WRITE_RESULT = {
    "type": "object",
    "required": ["artifact_id", "digest"],
    "properties": {"artifact_id": {"type": "string"}, "digest": {"type": "string"}},
}
LIST_SCHEMA = {"type": "object", "additionalProperties": False}
LIST_RESULT = {
    "type": "object",
    "required": ["artifact_ids"],
    "properties": {"artifact_ids": {"type": "array", "items": {"type": "string"}}},
}


class ArtifactStore:
    """File-backed store of canonical JSON artifacts keyed by their artifact id."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def path(self, artifact_id: str) -> Path:
        return self._root / f"{artifact_id}.json"

    def read(self, artifact_id: str) -> dict[str, Any]:
        path = self.path(artifact_id)
        if not path.is_file():
            raise KeyError(artifact_id)
        loaded: Any = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise TypeError(f"artifact {artifact_id} is not a JSON object")
        return loaded

    def write(self, document: Mapping[str, Any]) -> str:
        artifact_id = document.get("id")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise ValueError("document is missing a string 'id'")
        canonical = json.dumps(dict(document), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        self._root.mkdir(parents=True, exist_ok=True)
        self.path(artifact_id).write_bytes(canonical.encode("utf-8"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def list_ids(self) -> list[str]:
        if not self._root.is_dir():
            return []
        return sorted(path.stem for path in self._root.glob("*.json"))


def _read_handler(store: ArtifactStore) -> ToolHandler:
    def handler(args: Mapping[str, Any]) -> Mapping[str, Any]:
        artifact_id = str(args["artifact_id"])
        return {"artifact_id": artifact_id, "document": store.read(artifact_id)}

    return handler


def _write_handler(store: ArtifactStore) -> ToolHandler:
    def handler(args: Mapping[str, Any]) -> Mapping[str, Any]:
        document = dict(args["document"])
        errors = validate_artifact(document)
        if errors:
            raise ValueError("; ".join(errors))
        digest = store.write(document)
        return {"artifact_id": str(document["id"]), "digest": digest}

    return handler


def _list_handler(store: ArtifactStore) -> ToolHandler:
    def handler(args: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"artifact_ids": store.list_ids()}

    return handler


def register_artifact_tools(registry: ToolRegistry, store: ArtifactStore) -> None:
    """Register ``read_artifact``, ``write_artifact`` and ``list_artifacts`` on ``registry``."""
    registry.register(
        ToolSpec(
            name="read_artifact",
            scope="workspace",
            description="Read a canonical workflow artifact by id",
            args_schema=READ_SCHEMA,
            result_schema=READ_RESULT,
            handler=_read_handler(store),
        )
    )
    registry.register(
        ToolSpec(
            name="write_artifact",
            scope="workspace",
            description="Validate and persist a canonical workflow artifact",
            args_schema=WRITE_SCHEMA,
            result_schema=WRITE_RESULT,
            handler=_write_handler(store),
        )
    )
    registry.register(
        ToolSpec(
            name="list_artifacts",
            scope="workspace",
            description="List stored artifact ids",
            args_schema=LIST_SCHEMA,
            result_schema=LIST_RESULT,
            handler=_list_handler(store),
        )
    )


__all__ = ["ArtifactStore", "register_artifact_tools"]