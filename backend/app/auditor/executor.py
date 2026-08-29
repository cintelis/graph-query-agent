"""Executor: runs registry templates — and nothing else — with lineage.

Guarantees:

* Only ``Intent`` objects from the registry are executed; there is no code
  path that runs caller-supplied Cypher.
* Every session is opened with ``default_access_mode=READ`` — the driver
  routes to readers and the server rejects writes, on top of the templates
  themselves being MATCH/RETURN only. The target database belongs to
  another platform; this module must never mutate it.
* Every response carries lineage: request_id, graph_version (max updatedAt
  seen for the project), timing, attempt count and the exact intent@version
  that produced it.
"""

from __future__ import annotations

import json
import secrets
import time
from typing import Any

from neo4j import READ_ACCESS
from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired

from app.auditor.intents import Intent
from app.db.neo4j import get_driver

_MAX_ATTEMPTS = 2  # one retry on transient connectivity errors

# metadataJson keys that plausibly name the implementation target file.
_FILE_KEYS = ("file", "path", "targetFile", "filePath", "sourceFile", "target_file")


class ParamError(ValueError):
    """Raised when the caller's params do not satisfy the intent schema."""


def _new_request_id() -> str:
    return "req_" + secrets.token_hex(4)


def bind_params(intent: Intent, supplied: dict[str, Any]) -> dict[str, Any]:
    """Validate + bind params against the intent schema.

    Unknown params are rejected (nothing reaches the query that the schema
    does not declare); missing optional params are bound to ``None`` so the
    templates' ``$x IS NULL`` guards work; empty strings count as absent.
    """
    declared = {p.name for p in intent.params}
    unknown = set(supplied) - declared
    if unknown:
        raise ParamError(f"unknown params for {intent.ref}: {sorted(unknown)}")

    bound: dict[str, Any] = {}
    for p in intent.params:
        value = supplied.get(p.name)
        if isinstance(value, str):
            value = value.strip() or None
        if value is None:
            if p.required:
                raise ParamError(f"missing required param '{p.name}' for {intent.ref}")
            bound[p.name] = None
        elif isinstance(value, str):
            bound[p.name] = value
        else:
            raise ParamError(f"param '{p.name}' must be a string")
    return bound


def parse_metadata_json(raw: Any) -> dict[str, Any]:
    """Defensively parse a metadataJson property (may be missing/'{}'/garbage)."""
    if not raw or not isinstance(raw, str):
        return {}
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _extract_file(meta: dict[str, Any]) -> str | None:
    for key in _FILE_KEYS:
        value = meta.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _postprocess_rows(columns: list[str], rows: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    """Replace raw ``metadataJson`` columns with an extracted ``file`` column.

    Writers store metadataJson inconsistently (missing, '{}', arbitrary
    keys); the console only surfaces the target file when one is recorded.
    """
    if "metadataJson" not in columns:
        return columns, rows
    new_columns = [("file" if c == "metadataJson" else c) for c in columns]
    for row in rows:
        meta = parse_metadata_json(row.pop("metadataJson", None))
        row["file"] = _extract_file(meta)
    return new_columns, rows


async def _graph_version(session, project_id: str | None) -> str | None:
    """Cheap 'which graph answered' stamp: max node updatedAt in scope."""
    if project_id:
        cypher = (
            "MATCH (n:DesignNode {projectId: $projectId}) "
            "RETURN max(n.updatedAt) AS v"
        )
        result = await session.run(cypher, {"projectId": project_id})
    else:
        result = await session.run("MATCH (n:DesignNode) RETURN max(n.updatedAt) AS v")
    record = await result.single()
    return record["v"] if record else None


async def execute(intent: Intent, supplied_params: dict[str, Any]) -> dict[str, Any]:
    """Run one registry template read-only and return rows + full lineage."""
    if not intent.read_only:  # defense in depth; every registered intent is read-only
        raise ParamError(f"{intent.ref} is not read-only; refusing to execute")

    params = bind_params(intent, supplied_params)
    request_id = _new_request_id()
    started = time.perf_counter()

    attempts = 0
    last_error: Exception | None = None
    driver = get_driver()
    while attempts < _MAX_ATTEMPTS:
        attempts += 1
        try:
            async with driver.session(default_access_mode=READ_ACCESS) as session:
                result = await session.run(intent.cypher, params)
                columns = list(result.keys())
                rows = [dict(record) async for record in result]
                graph_version = await _graph_version(session, params.get("projectId"))
            break
        except (ServiceUnavailable, SessionExpired) as exc:
            last_error = exc
            continue
        except Neo4jError:
            raise
    else:
        assert last_error is not None
        raise last_error

    columns, rows = _postprocess_rows(columns, rows)
    timing_ms = round((time.perf_counter() - started) * 1000, 1)

    return {
        "rows": rows,
        "columns": columns,
        "row_count": len(rows),
        "cypher": intent.cypher,
        "params": params,
        "lineage": {
            "request_id": request_id,
            "graph_version": graph_version,
            "timing_ms": timing_ms,
            "attempts": attempts,
            "produced_by": intent.ref,
            "source": "neo4j",
            "read_only": True,
        },
    }
