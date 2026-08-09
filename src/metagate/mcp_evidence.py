"""Normalize entity payloads returned by DataHub-compatible MCP servers.

MCP tool results are transport-shaped, not MetaGate-shaped.  This module
keeps that boundary explicit: it accepts ``structuredContent`` and text JSON
blocks, finds the requested entity, and reports only facts that were actually
returned by the server.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable


EVIDENCE_FIELDS = (
    "description",
    "ownership",
    "glossary",
    "domain",
    "tags",
    "lineage",
    "column_lineage",
    "assertions",
    "freshness",
    "incidents",
    "usage",
    "policy",
)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _nonempty(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _identifier(value: Any) -> str | None:
    if isinstance(value, str):
        return value or None
    if isinstance(value, dict):
        for key in ("urn", "name", "username", "id", "fieldPath"):
            if value.get(key):
                return str(value[key])
    return None


def _decode_content(payload: Any) -> tuple[list[dict[str, Any]], int, list[str]]:
    """Collect JSON objects from MCP structured content and text blocks."""
    objects: list[dict[str, Any]] = []
    text_count = 0
    notes: list[str] = []

    def visit(value: Any) -> None:
        nonlocal text_count
        if isinstance(value, dict):
            if value.get("type") == "text" and isinstance(value.get("text"), str):
                text_count += 1
                text = value["text"].strip()
                try:
                    decoded = json.loads(text)
                except json.JSONDecodeError:
                    if text:
                        notes.append("MCP returned a non-JSON text block; it was not treated as evidence.")
                    return
                visit(decoded)
                return
            objects.append(value)
            for child in value.values():
                if isinstance(child, (dict, list)):
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(payload)
    return objects, text_count, notes


def _find_entity(objects: Iterable[dict[str, Any]], urn: str) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("urn") == urn:
                candidates.append(value)
            for child in value.values():
                if isinstance(child, (dict, list)):
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for item in objects:
        visit(item)
    if candidates:
        return max(candidates, key=lambda item: len(item))
    return None


def _field(entity: dict[str, Any], *keys: str) -> tuple[bool, Any]:
    for key in keys:
        if key in entity:
            return True, entity[key]
    properties = entity.get("properties")
    if isinstance(properties, dict):
        for key in keys:
            if key in properties:
                return True, properties[key]
    return False, None


def _owners(value: Any) -> list[str]:
    if isinstance(value, dict):
        value = value.get("owners", value.get("owner", []))
    result = []
    for item in _as_list(value):
        if isinstance(item, dict):
            item = item.get("owner", item)
        identifier = _identifier(item)
        if identifier:
            result.append(identifier)
    return sorted(set(result))


def _terms(value: Any) -> list[str]:
    if isinstance(value, dict):
        if not any(key in value for key in ("terms", "glossaryTerms")):
            identifier = _identifier(value)
            return [identifier] if identifier else []
        value = value.get("terms", value.get("glossaryTerms", []))
    result = []
    for item in _as_list(value):
        if isinstance(item, dict):
            item = item.get("term", item)
        identifier = _identifier(item)
        if identifier:
            result.append(identifier)
    return sorted(set(result))


def _links(value: Any, key: str) -> list[str]:
    if isinstance(value, dict):
        value = value.get(key, value.get("entities", []))
    result = []
    for item in _as_list(value):
        if isinstance(item, dict):
            item = item.get("entity", item)
        identifier = _identifier(item)
        if identifier:
            result.append(identifier)
    return sorted(set(result))


def _latest_assertions(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = value.get("assertions", value.get("results", value.get("latest_results", [])))
    latest: dict[str, dict[str, Any]] = {}
    for index, assertion in enumerate(_as_list(value)):
        if not isinstance(assertion, dict):
            continue
        events = assertion.get("runEvents", assertion.get("events", []))
        events = events.get("runEvents", []) if isinstance(events, dict) else events
        rows = _as_list(events) or [assertion]
        row = max(rows, key=lambda item: str(item.get("timestampMillis", item.get("timestamp", ""))) if isinstance(item, dict) else "")
        if not isinstance(row, dict):
            continue
        name = str(assertion.get("urn") or assertion.get("name") or assertion.get("assertion_urn") or index)
        latest[name] = {
            "assertion_urn": assertion.get("urn"),
            "name": assertion.get("name") or assertion.get("urn"),
            "status": row.get("status") or (row.get("result") or {}).get("type"),
            "timestamp": row.get("timestamp") or row.get("timestampMillis"),
        }
    return list(latest.values())


def _status(present: bool, value: Any, *, available: bool = True) -> str:
    if not available:
        return "unavailable"
    return "present" if present and _nonempty(value) else "absent"


def normalize_mcp_entity_output(payload: Any, urn: str) -> dict[str, Any]:
    """Return evidence facts from one MCP ``get_entities`` result.

    Missing fields are deliberately ``unavailable`` rather than ``absent``:
    the official MCP may expose a smaller entity shape than GraphQL, and an
    omitted field is not proof that the metadata does not exist.
    """
    objects, text_count, notes = _decode_content(payload)
    entity = _find_entity(objects, urn)
    if entity is None:
        return {
            "status": "attention_required",
            "checked_urn": urn,
            "entity_found": False,
            "content_blocks": text_count,
            "returned_fields": [],
            "evidence": {},
            "facts": {},
            "notes": notes + ["MCP did not return the requested asset URN."],
        }

    now = datetime.now(timezone.utc).isoformat()
    facts: dict[str, Any] = {"urn": urn, "type": entity.get("type", "dataset")}
    evidence: dict[str, dict[str, Any]] = {}

    def add(kind: str, value: Any, *, available: bool, detail: dict[str, Any] | None = None) -> None:
        details = detail or {}
        evidence[kind] = {
            "status": _status(_nonempty(value), value, available=available),
            "source": "DataHub official MCP get_entities",
            "observed_at": now,
            **details,
        }

    found, value = _field(entity, "description")
    description = value.get("text", value.get("description", "")) if isinstance(value, dict) else value
    facts["description"] = description
    add("description", description, available=found)

    found, value = _field(entity, "ownership")
    owners = _owners(value)
    facts["ownership"] = {"owners": owners}
    add("ownership", owners, available=found, detail={"owners": owners})

    found, value = _field(entity, "glossaryTerms", "glossary", "terms")
    terms = _terms(value)
    facts["glossary"] = {"terms": terms}
    add("glossary", terms, available=found, detail={"terms": terms})

    found, value = _field(entity, "domain")
    domains = _terms(value)
    facts["domain"] = {"domains": domains}
    add("domain", domains, available=found, detail={"domains": domains})

    found, value = _field(entity, "tags")
    tags = _terms(value)
    facts["tags"] = {"tags": tags}
    add("tags", tags, available=found, detail={"tags": tags})

    up_found, upstream_value = _field(entity, "upstreamLineage", "upstreams")
    down_found, downstream_value = _field(entity, "downstreamLineage", "downstreams")
    upstreams = _links(upstream_value, "upstreams")
    downstreams = _links(downstream_value, "downstreams")
    facts["lineage"] = {"upstreams": upstreams, "downstreams": downstreams}
    add("lineage", upstreams + downstreams, available=up_found or down_found, detail={"upstreams": upstreams, "downstreams": downstreams})

    schema_found, schema = _field(entity, "schemaMetadata", "schema", "fields")
    fgl_found, fgl = _field(entity, "fineGrainedLineages", "columnLineage", "column_lineage")
    fields = schema.get("fields", []) if isinstance(schema, dict) else _as_list(schema)
    field_names = [item.get("fieldPath") or item.get("name") for item in fields if isinstance(item, dict)]
    mappings = _as_list(fgl.get("fineGrainedLineages", fgl) if isinstance(fgl, dict) else fgl)
    mapped = [item for item in mappings if isinstance(item, dict)]
    mapped_names = {
        identifier
        for item in mapped
        for candidate in _as_list(item.get("downstreams", item.get("fields", [])))
        for identifier in [_identifier(candidate)]
        if identifier
    }
    missing = sorted(set(field_names) - mapped_names)
    facts["column_lineage"] = {"fields": field_names, "mapping_count": len(mapped), "missing_columns": missing}
    add("column_lineage", field_names or mapped, available=schema_found or fgl_found, detail=facts["column_lineage"])

    found, value = _field(entity, "assertions", "qualityAssertions")
    latest = _latest_assertions(value)
    facts["assertions"] = {"latest_results": latest, "count": len(latest)}
    add("assertions", latest, available=found, detail=facts["assertions"])

    found, value = _field(entity, "freshness", "freshnessState", "lastUpdated")
    freshness = value if isinstance(value, dict) else {"timestamp": value}
    facts["freshness"] = freshness
    add("freshness", freshness.get("timestamp") or freshness.get("observed_at"), available=found, detail=freshness)

    found, value = _field(entity, "incidents", "activeIncidents")
    incidents = value.get("incidents", value) if isinstance(value, dict) else value
    incidents = _as_list(incidents)
    facts["incidents"] = {"open": len(incidents), "items": incidents}
    add("incidents", incidents, available=found, detail=facts["incidents"])
    if found:
        evidence["incidents"]["status"] = "open" if incidents else "clear"

    found, value = _field(entity, "usageStats", "usage")
    usage = value if isinstance(value, dict) else {"value": value}
    facts["usage"] = usage
    add("usage", usage, available=found, detail=usage)

    found, value = _field(entity, "policy", "accessPolicy")
    facts["policy"] = value or {}
    add("policy", value, available=found)

    return {
        "status": "verified",
        "checked_urn": urn,
        "entity_found": True,
        "content_blocks": text_count,
        "returned_fields": sorted(entity.keys()),
        "evidence": evidence,
        "facts": facts,
        "notes": notes,
    }


def normalize_mcp_query_output(payload: Any) -> dict[str, Any]:
    """Reduce MCP query-history output to safe usage evidence.

    Query text is deliberately discarded. MetaGate only needs to know
    whether usage exists and when the most recent query was observed.
    """
    objects, text_count, notes = _decode_content(payload)
    query_rows: list[dict[str, Any]] = []
    recognized = False
    containers = ("queries", "results", "datasetQueries", "queryHistory", "query_history")

    def visit(value: Any) -> None:
        nonlocal recognized
        if isinstance(value, dict):
            for key in containers:
                if key in value:
                    recognized = True
                    query_rows.extend(item for item in _as_list(value[key]) if isinstance(item, dict))
            for child in value.values():
                if isinstance(child, (dict, list)):
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for item in objects:
        visit(item)

    if not recognized and objects:
        candidate_keys = {key for item in objects for key in item}
        if candidate_keys.intersection({"query", "queryText", "timestamp", "timestampMillis", "executedAt"}):
            query_rows = objects
            recognized = True

    timestamps = [
        row.get("timestamp") or row.get("timestampMillis") or row.get("executedAt")
        for row in query_rows
        if isinstance(row, dict)
    ]
    timestamps = [value for value in timestamps if value not in (None, "")]
    latest = max((str(value) for value in timestamps), default=None)
    if recognized:
        status = "present" if query_rows else "absent"
    else:
        status = "unavailable"
        notes.append("MCP query-history response shape was not recognized; usage was not inferred.")
    return {
        "status": status,
        "query_count": len(query_rows),
        "latest_query_at": latest,
        "content_blocks": text_count,
        "notes": notes,
    }
