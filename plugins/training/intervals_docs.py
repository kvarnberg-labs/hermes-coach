"""intervals.icu API documentation access for Hermes Coach.

Fetches the public OpenAPI 3.0.1 spec from intervals.icu and exposes two
tools so Hermes can discover and inspect API endpoints at runtime:

  search_intervals_api_docs   — keyword search across operations (or tag overview)
  get_intervals_api_endpoint  — full detail for one operation with schemas resolved

The spec is fetched once and memoised with a 6-hour TTL; no API key required.

Spec URL: https://intervals.icu/api/v1/docs
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any, Optional

logger = logging.getLogger(__name__)

_SPEC_URL = "https://intervals.icu/api/v1/docs"
_CACHE_TTL: float = 6 * 3600  # seconds — spec is near-static
_MAX_REF_DEPTH = 6

_spec: dict[str, Any] | None = None
_op_index: list[dict[str, str]] | None = None
_cache_time: float = 0.0


def _fetch_spec() -> dict[str, Any]:
    """Fetch the OpenAPI spec, memoised for _CACHE_TTL seconds."""
    global _spec, _op_index, _cache_time
    now = time.monotonic()
    if _spec is not None and (now - _cache_time) < _CACHE_TTL:
        return _spec

    req = urllib.request.Request(
        _SPEC_URL,
        headers={"User-Agent": "hermes-coach/1.0", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach intervals.icu spec: {exc.reason}") from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"intervals.icu spec returned non-JSON: {exc}") from exc

    _spec = data
    _op_index = _build_index(data)
    _cache_time = now
    return data


def _build_index(spec: dict[str, Any]) -> list[dict[str, str]]:
    """Flatten all HTTP operations into a searchable list."""
    ops: list[dict[str, str]] = []
    for path, methods in spec.get("paths", {}).items():
        for method, op in methods.items():
            if method.upper() not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                continue
            tags = op.get("tags", ["(none)"])
            ops.append({
                "method": method.upper(),
                "path": path,
                "operationId": op.get("operationId", ""),
                "tag": tags[0] if tags else "(none)",
                "summary": op.get("summary", ""),
            })
    return ops


def _load_index() -> tuple[dict[str, Any], list[dict[str, str]]]:
    """Return (spec, op_index), fetching if needed."""
    spec = _fetch_spec()
    if _op_index is None:
        raise RuntimeError("op_index not initialised alongside _spec — this is a bug")
    return spec, _op_index


def _score(entry: dict[str, str], keywords: list[str]) -> int:
    """Count keywords found in the entry's combined searchable text."""
    haystack = (
        f"{entry['summary']} {entry['path']} {entry['operationId']} {entry['tag']}"
    ).lower()
    return sum(1 for kw in keywords if kw in haystack)


def _resolve_refs(
    obj: Any,
    schemas: dict[str, Any],
    visited: frozenset[str],
    depth: int,
) -> Any:
    """Resolve $ref pointers in a schema fragment.

    Recurses into dicts and lists. Replaces circular refs with a cycle stub and
    overly deep $ref chains with a truncation stub. Only $ref hops count toward
    depth — structural dict/list traversal does not, so plain values (enum
    strings, integers) are never replaced by stubs.
    """
    if isinstance(obj, dict):
        if "$ref" in obj:
            ref = obj["$ref"]
            if not ref.startswith("#/components/schemas/"):
                return obj  # external ref — leave as-is
            name = ref.split("/")[-1]
            if name in visited:
                return {"$ref": name}  # cycle stub
            if depth > _MAX_REF_DEPTH:
                return {"$ref_truncated": "(max depth reached)"}
            schema = schemas.get(name)
            if schema is None:
                return {"$ref_unknown": name}
            return _resolve_refs(schema, schemas, visited | {name}, depth + 1)

        # Structural dict — depth unchanged; only $ref hops increment it
        return {k: _resolve_refs(v, schemas, visited, depth) for k, v in obj.items()}

    if isinstance(obj, list):
        return [_resolve_refs(item, schemas, visited, depth) for item in obj]

    return obj


def search_intervals_api_docs(query: str, limit: int = 10, **_: Any) -> str:
    """Search the intervals.icu API spec for matching operations.

    When query is empty or very short (< 3 chars), returns a tag overview
    (tag → operation count) so the caller can discover API categories.

    Args:
        query: Keyword(s) to search for, e.g. 'wellness', 'power curve'.
        limit: Max results to return (default 10).
    """
    limit = max(1, limit)
    try:
        spec, index = _load_index()
    except RuntimeError as exc:
        return json.dumps({"error": str(exc)})

    if len(query.strip()) < 3:
        tags: dict[str, int] = {}
        for op in index:
            tags[op["tag"]] = tags.get(op["tag"], 0) + 1
        return json.dumps({
            "note": "Query too short — showing tag overview. Search by tag name or keyword.",
            "tags": tags,
            "total_operations": len(index),
        })

    keywords = query.lower().split()
    scored = [(entry, _score(entry, keywords)) for entry in index]
    scored = [(e, s) for e, s in scored if s > 0]
    scored.sort(key=lambda x: -x[1])
    results = [e for e, _ in scored[:limit]]

    if not results:
        available = sorted({op["tag"] for op in index})
        return json.dumps({
            "query": query,
            "matched": False,
            "available_tags": available,
            "note": "No operations matched. Try a tag name or a different keyword.",
        })

    return json.dumps({
        "query": query,
        "matched": len(results),
        "operations": results,
    })


def get_intervals_api_endpoint(
    operation_id: Optional[str] = None,
    method: Optional[str] = None,
    path: Optional[str] = None,
    **_: Any,
) -> str:
    """Return full details for one intervals.icu API operation.

    Identify the operation by operationId (preferred), or by method + path.
    Returns description, parameters, request-body schema, and response schemas
    with $refs resolved inline.

    Args:
        operation_id: The operationId, e.g. 'getRecord'.
        method:       HTTP method, e.g. 'GET'. Used with path when operationId absent.
        path:         URL path, e.g. '/api/v1/athlete/{id}/wellness/{date}'.
    """
    try:
        spec, index = _load_index()
    except RuntimeError as exc:
        return json.dumps({"error": str(exc)})

    match: dict[str, str] | None = None
    if operation_id:
        oid_lower = operation_id.lower()
        for entry in index:
            if entry["operationId"].lower() == oid_lower:
                match = entry
                break
    elif method and path:
        m_upper = method.upper()
        for entry in index:
            if entry["method"] == m_upper and entry["path"] == path:
                match = entry
                break

    if match is None:
        return json.dumps({
            "error": "Operation not found. Use search_intervals_api_docs to find the operationId.",
            "searched_by": {"operation_id": operation_id, "method": method, "path": path},
        })

    raw_op = spec["paths"][match["path"]][match["method"].lower()]
    schemas = spec.get("components", {}).get("schemas", {})

    def resolve(obj: Any) -> Any:
        return _resolve_refs(obj, schemas, frozenset(), 0)

    params = []
    for p in raw_op.get("parameters", []):
        params.append({
            "name": p.get("name"),
            "in": p.get("in"),
            "required": p.get("required", False),
            "description": p.get("description", ""),
            "schema": resolve(p.get("schema", {})),
        })

    request_body = None
    if "requestBody" in raw_op:
        rb = raw_op["requestBody"]
        content = rb.get("content", {})
        schema_raw = (
            content.get("application/json", {}).get("schema")
            or next(iter(content.values()), {}).get("schema")
        )
        request_body = {
            "required": rb.get("required", False),
            "schema": resolve(schema_raw) if schema_raw else None,
        }

    responses: dict[str, Any] = {}
    for status, resp in raw_op.get("responses", {}).items():
        content = resp.get("content", {})
        schema_raw = (
            content.get("application/json", {}).get("schema")
            or content.get("*/*", {}).get("schema")
            or (next(iter(content.values()), {}).get("schema") if content else None)
        )
        responses[status] = {
            "description": resp.get("description", ""),
            "schema": resolve(schema_raw) if schema_raw else None,
        }

    return json.dumps({
        "method": match["method"],
        "path": match["path"],
        "operationId": match["operationId"],
        "tag": match["tag"],
        "summary": match["summary"],
        "description": raw_op.get("description", ""),
        "parameters": params,
        "requestBody": request_body,
        "responses": responses,
    })


def register_tools(ctx) -> None:
    ctx.register_tool(
        name="search_intervals_api_docs",
        toolset="training",
        schema={
            "name": "search_intervals_api_docs",
            "description": (
                "Search the official intervals.icu OpenAPI spec for API operations "
                "matching a keyword. Returns matching endpoints (method, path, "
                "operationId, tag, summary). Use get_intervals_api_endpoint to fetch "
                "full parameter and schema details for a specific operation. "
                "An empty or very short query returns a tag overview so you can "
                "discover available API categories (Activities, Wellness, Events, etc.)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Keyword(s) to search for, e.g. 'wellness', 'power curve', "
                            "'planned event', 'athlete profile'. Leave empty to get a "
                            "tag overview."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results to return (default 10).",
                    },
                },
                "required": ["query"],
            },
        },
        handler=lambda args, **kw: search_intervals_api_docs(
            query=args.get("query", ""),
            limit=max(1, int(args.get("limit", 10) or 10)),
        ),
    )

    ctx.register_tool(
        name="get_intervals_api_endpoint",
        toolset="training",
        schema={
            "name": "get_intervals_api_endpoint",
            "description": (
                "Fetch full details for one intervals.icu API operation: description, "
                "path and query parameters, request-body schema, and response schemas — "
                "with $ref pointers resolved inline. Use the operationId from "
                "search_intervals_api_docs, or supply method + path."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "operation_id": {
                        "type": "string",
                        "description": "The operationId, e.g. 'getRecord', 'listActivities'.",
                    },
                    "method": {
                        "type": "string",
                        "description": "HTTP method (GET/POST/PUT/DELETE). Use with path.",
                    },
                    "path": {
                        "type": "string",
                        "description": "URL path, e.g. '/api/v1/athlete/{id}/wellness/{date}'.",
                    },
                },
                "required": [],
            },
        },
        handler=lambda args, **kw: get_intervals_api_endpoint(
            operation_id=args.get("operation_id"),
            method=args.get("method"),
            path=args.get("path"),
        ),
    )
