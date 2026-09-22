"""Contract tests for the request-creation golden path (M1, TASK-0002).

Covers the three runtime contracts: OpenAPI (REST), Protobuf (gRPC), and the
RequestCreated domain event schema. The event schema and its golden example are
validated independently of the workflow-artifact registry.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from sdlc.artifacts import find_repo_root

REPO_ROOT = find_repo_root()
CONTRACTS = REPO_ROOT / "contracts"


def _load_json(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def _event_schema() -> dict[str, Any]:
    return _load_json(CONTRACTS / "events" / "request-created.schema.json")


def _event_example() -> dict[str, Any]:
    return _load_json(CONTRACTS / "events" / "examples" / "request-created.json")


def _openapi() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(
        (CONTRACTS / "openapi" / "requests.yaml").read_text(encoding="utf-8")
    )
    return loaded


def _ref_name(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


def test_event_schema_is_valid_draft_2020_12() -> None:
    Draft202012Validator.check_schema(_event_schema())


def test_event_example_validates() -> None:
    validator = Draft202012Validator(_event_schema(), format_checker=FormatChecker())
    assert list(validator.iter_errors(_event_example())) == []


def test_event_example_rejects_unknown_status() -> None:
    example = _event_example()
    example["request"]["status"] = "archived"
    validator = Draft202012Validator(_event_schema(), format_checker=FormatChecker())
    assert list(validator.iter_errors(example)), "unknown status must be rejected"


def test_openapi_is_3_1_and_exposes_create_request() -> None:
    spec = _openapi()
    assert str(spec["openapi"]).startswith("3.1")
    post = spec["paths"]["/requests"]["post"]
    body = post["requestBody"]["content"]["application/json"]["schema"]
    response = post["responses"]["201"]["content"]["application/json"]["schema"]
    assert _ref_name(body["$ref"]) == "CreateRequest"
    assert _ref_name(response["$ref"]) == "Request"
    assert "bearerAuth" in spec["components"]["securitySchemes"]


def test_openapi_schemas_match_event_contract() -> None:
    schemas = _openapi()["components"]["schemas"]
    assert schemas["CreateRequest"]["required"] == ["title"]
    assert set(schemas["Request"]["required"]) == {"id", "title", "status", "created_at"}
    request_props = set(schemas["Request"]["properties"])
    event_request_props = set(_event_schema()["properties"]["request"]["properties"])
    assert request_props == event_request_props, "REST resource and event payload must agree"


def test_proto_declares_domain_service_and_messages() -> None:
    text = (CONTRACTS / "proto" / "domain" / "v1" / "domain.proto").read_text(encoding="utf-8")
    assert 'syntax = "proto3";' in text
    assert "package domain.v1;" in text
    assert "service DomainService" in text
    assert "rpc CreateRequest(CreateRequestRequest) returns (CreateRequestResponse)" in text
    assert "message RequestCreated" in text