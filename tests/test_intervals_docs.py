"""Tests for intervals_docs — hermetic, no network."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "plugins"))

import training.intervals_docs as mod
from training.intervals_docs import (
    _build_index,
    _resolve_refs,
    get_intervals_api_endpoint,
    search_intervals_api_docs,
)

# ---------------------------------------------------------------------------
# Minimal fixture spec — realistic shape, small enough to reason about.
# ---------------------------------------------------------------------------
_FIXTURE_SPEC: dict[str, Any] = {
    "openapi": "3.0.1",
    "info": {"title": "Intervals.icu API", "version": "v1.0.0"},
    "paths": {
        "/api/v1/athlete/{id}/wellness/{date}": {
            "get": {
                "tags": ["Wellness"],
                "summary": "Get wellness record for a date",
                "operationId": "getRecord",
                "description": "Returns CTL, ATL, TSB and HRV for the given date.",
                "parameters": [
                    {
                        "name": "id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                    {
                        "name": "date",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string", "format": "date"},
                    },
                ],
                "responses": {
                    "200": {
                        "description": "OK",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/WellnessRecord"}
                            }
                        },
                    }
                },
            }
        },
        "/api/v1/athlete/{id}/activities": {
            "get": {
                "tags": ["Activities"],
                "summary": "List recent activities",
                "operationId": "listActivities",
                "parameters": [],
                "responses": {"200": {"description": "OK"}},
            },
            "post": {
                "tags": ["Activities"],
                "summary": "Create an activity",
                "operationId": "createActivity",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {"$ref": "#/components/schemas/Activity"}
                        }
                    },
                },
                "responses": {"200": {"description": "OK"}},
            },
        },
    },
    "components": {
        "schemas": {
            "WellnessRecord": {
                "type": "object",
                "properties": {
                    "ctl": {"type": "number"},
                    "atl": {"type": "number"},
                    "tsb": {"type": "number"},
                },
            },
            "Activity": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    # Self-referential to test cycle guard
                    "parentActivity": {"$ref": "#/components/schemas/Activity"},
                },
            },
        }
    },
}


@pytest.fixture(autouse=True)
def reset_cache(monkeypatch: pytest.MonkeyPatch):
    """Reset module-level memoisation before every test."""
    monkeypatch.setattr(mod, "_spec", None)
    monkeypatch.setattr(mod, "_op_index", None)
    monkeypatch.setattr(mod, "_cache_time", 0.0)


@pytest.fixture
def patched_fetch(monkeypatch: pytest.MonkeyPatch):
    """Patch _fetch_spec to return the fixture spec without any network call."""

    def _fake_fetch() -> dict[str, Any]:
        mod._spec = _FIXTURE_SPEC
        mod._op_index = _build_index(_FIXTURE_SPEC)
        mod._cache_time = 9_999_999_999.0  # far future, won't expire during test
        return _FIXTURE_SPEC

    monkeypatch.setattr(mod, "_fetch_spec", _fake_fetch)
    yield


# ---------------------------------------------------------------------------
# _build_index
# ---------------------------------------------------------------------------
class TestBuildIndex:
    def test_flattens_all_http_methods(self):
        index = _build_index(_FIXTURE_SPEC)
        ops = {e["operationId"] for e in index}
        assert ops == {"getRecord", "listActivities", "createActivity"}

    def test_method_is_uppercase(self):
        index = _build_index(_FIXTURE_SPEC)
        for entry in index:
            assert entry["method"] == entry["method"].upper()

    def test_tag_is_first_tag(self):
        index = _build_index(_FIXTURE_SPEC)
        entry = next(e for e in index if e["operationId"] == "getRecord")
        assert entry["tag"] == "Wellness"

    def test_absent_tags_field_defaults_to_none_tag(self):
        spec = {
            "paths": {
                "/api/v1/foo": {
                    "get": {"operationId": "getFoo", "summary": "Foo"}
                }
            }
        }
        index = _build_index(spec)
        assert index[0]["tag"] == "(none)"


# ---------------------------------------------------------------------------
# search_intervals_api_docs
# ---------------------------------------------------------------------------
class TestSearch:
    def test_empty_query_returns_tag_overview(self, patched_fetch):
        result = json.loads(search_intervals_api_docs(query=""))
        assert "tags" in result
        assert result["tags"]["Wellness"] == 1
        assert result["tags"]["Activities"] == 2

    def test_very_short_query_returns_tag_overview(self, patched_fetch):
        result = json.loads(search_intervals_api_docs(query="ac"))
        assert "tags" in result

    def test_keyword_match_returns_operations(self, patched_fetch):
        result = json.loads(search_intervals_api_docs(query="wellness"))
        assert result["matched"] >= 1
        ids = [op["operationId"] for op in result["operations"]]
        assert "getRecord" in ids

    def test_no_match_returns_available_tags(self, patched_fetch):
        result = json.loads(search_intervals_api_docs(query="zzznomatch"))
        assert result["matched"] is False
        assert "available_tags" in result

    def test_limit_is_respected(self, patched_fetch):
        result = json.loads(search_intervals_api_docs(query="activity", limit=1))
        assert len(result["operations"]) <= 1

    def test_fetch_error_returns_json_error(self, monkeypatch: pytest.MonkeyPatch):
        def _fail() -> dict[str, Any]:
            raise RuntimeError("Could not reach intervals.icu spec: timed out")

        monkeypatch.setattr(mod, "_fetch_spec", _fail)
        result = json.loads(search_intervals_api_docs(query="wellness"))
        assert "error" in result

    def test_no_match_tag_hint_lists_all_tags(self, patched_fetch):
        result = json.loads(search_intervals_api_docs(query="zzznomatch"))
        assert set(result["available_tags"]) == {"Wellness", "Activities"}


# ---------------------------------------------------------------------------
# get_intervals_api_endpoint
# ---------------------------------------------------------------------------
class TestGetEndpoint:
    def test_lookup_by_operation_id(self, patched_fetch):
        result = json.loads(get_intervals_api_endpoint(operation_id="getRecord"))
        assert result["operationId"] == "getRecord"
        assert result["method"] == "GET"
        assert len(result["parameters"]) == 2

    def test_lookup_by_method_and_path(self, patched_fetch):
        result = json.loads(
            get_intervals_api_endpoint(
                method="POST",
                path="/api/v1/athlete/{id}/activities",
            )
        )
        assert result["operationId"] == "createActivity"

    def test_response_schema_ref_is_resolved(self, patched_fetch):
        result = json.loads(get_intervals_api_endpoint(operation_id="getRecord"))
        schema = result["responses"]["200"]["schema"]
        assert schema.get("type") == "object"
        assert "ctl" in schema["properties"]

    def test_request_body_schema_returned(self, patched_fetch):
        result = json.loads(get_intervals_api_endpoint(operation_id="createActivity"))
        assert result["requestBody"] is not None
        assert result["requestBody"]["required"] is True

    def test_not_found_returns_error(self, patched_fetch):
        result = json.loads(get_intervals_api_endpoint(operation_id="doesNotExist"))
        assert "error" in result

    def test_no_args_returns_error(self, patched_fetch):
        result = json.loads(get_intervals_api_endpoint())
        assert "error" in result

    def test_operation_id_lookup_is_case_insensitive(self, patched_fetch):
        result = json.loads(get_intervals_api_endpoint(operation_id="GETRECORD"))
        assert result["operationId"] == "getRecord"

    def test_fetch_error_returns_json_error(self, monkeypatch: pytest.MonkeyPatch):
        def _fail() -> dict[str, Any]:
            raise RuntimeError("Could not reach intervals.icu spec: timed out")

        monkeypatch.setattr(mod, "_fetch_spec", _fail)
        result = json.loads(get_intervals_api_endpoint(operation_id="getRecord"))
        assert "error" in result


# ---------------------------------------------------------------------------
# _resolve_refs
# ---------------------------------------------------------------------------
class TestResolveRefs:
    def setup_method(self):
        self.schemas = _FIXTURE_SPEC["components"]["schemas"]

    def test_resolves_simple_ref(self):
        obj = {"$ref": "#/components/schemas/WellnessRecord"}
        result = _resolve_refs(obj, self.schemas, frozenset(), 0)
        assert result["type"] == "object"
        assert "ctl" in result["properties"]

    def test_cycle_guard_returns_stub(self):
        # Activity.parentActivity points back to Activity — should produce a stub
        obj = {"$ref": "#/components/schemas/Activity"}
        result = _resolve_refs(obj, self.schemas, frozenset(), 0)
        parent = result["properties"]["parentActivity"]
        assert parent == {"$ref": "Activity"}

    def test_max_depth_returns_truncated(self):
        obj = {"$ref": "#/components/schemas/WellnessRecord"}
        result = _resolve_refs(obj, self.schemas, frozenset(), mod._MAX_REF_DEPTH + 1)
        assert "$ref_truncated" in result

    def test_scalar_at_any_depth_not_truncated(self):
        # Scalars should pass through regardless of structural depth — the guard
        # only applies to $ref hops, not to plain values like enum strings.
        for v in ("Ride", 42, True, None):
            assert _resolve_refs(v, self.schemas, frozenset(), mod._MAX_REF_DEPTH + 10) == v

    def test_unknown_ref_returns_unknown_stub(self):
        obj = {"$ref": "#/components/schemas/DoesNotExist"}
        result = _resolve_refs(obj, self.schemas, frozenset(), 0)
        assert result == {"$ref_unknown": "DoesNotExist"}

    def test_non_ref_dict_recurses(self):
        obj = {
            "type": "object",
            "properties": {"x": {"$ref": "#/components/schemas/WellnessRecord"}},
        }
        result = _resolve_refs(obj, self.schemas, frozenset(), 0)
        assert result["properties"]["x"]["type"] == "object"

    def test_list_recurses(self):
        obj = [{"$ref": "#/components/schemas/WellnessRecord"}]
        result = _resolve_refs(obj, self.schemas, frozenset(), 0)
        assert result[0]["type"] == "object"

    def test_primitives_returned_as_is(self):
        assert _resolve_refs("hello", {}, frozenset(), 0) == "hello"
        assert _resolve_refs(42, {}, frozenset(), 0) == 42
        assert _resolve_refs(None, {}, frozenset(), 0) is None

    def test_external_ref_left_as_is(self):
        obj = {"$ref": "https://example.com/schema.json"}
        result = _resolve_refs(obj, self.schemas, frozenset(), 0)
        assert result == obj
