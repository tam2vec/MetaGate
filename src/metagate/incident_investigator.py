"""Evidence-backed incident investigation across the available lineage graph."""

from __future__ import annotations

from typing import Any


def _incident_rows(facts: dict[str, Any]) -> list[dict[str, Any]]:
    value = facts.get("incidents") or {}
    if not isinstance(value, dict):
        return []
    rows = value.get("items") or value.get("incidents") or value.get("rows") or []
    if isinstance(rows, dict):
        rows = [rows]
    return [row for row in rows if isinstance(row, dict)]


def _asset(run: dict[str, Any]) -> str | None:
    return run.get("entity_urn") or run.get("urn")


def _lineage_candidates(lineage: dict[str, Any]) -> list[dict[str, Any]]:
    values: list[Any] = []
    for key in ("upstreams", "upstream_entities", "upstream", "downstreams", "downstream_entities", "downstream"):
        value = lineage.get(key) or []
        values.extend(value if isinstance(value, list) else [value])
    result: list[dict[str, Any]] = []
    for value in values:
        if isinstance(value, str):
            result.append({"urn": value, "relationship": "lineage"})
        elif isinstance(value, dict):
            urn = value.get("urn") or value.get("entity_urn") or value.get("entity", {}).get("urn")
            if urn:
                result.append({"urn": str(urn), "relationship": value.get("relationship") or "lineage"})
    return list({item["urn"]: item for item in result}.values())


def investigate(run: dict[str, Any], max_depth: int = 3) -> dict[str, Any]:
    """Find the closest known failing fact and its lineage path.

    The function never invents a root cause. If DataHub did not return incident
    or lineage facts, it reports that limitation explicitly.
    """
    facts = run.get("facts") or (run.get("assessment") or {}).get("facts") or {}
    incidents = _incident_rows(facts)
    lineage = facts.get("lineage") if isinstance(facts, dict) else {}
    if not isinstance(lineage, dict):
        lineage = {}
    candidates = _lineage_candidates(lineage)
    upstream_names = [item["urn"] for item in candidates]
    asset = _asset(run)
    incident_summary = facts.get("incidents") if isinstance(facts.get("incidents"), dict) else {}
    open_count = incident_summary.get("open", incident_summary.get("open_count"))
    if not incidents:
        if open_count is None:
            status = "incident_evidence_unavailable"
            finding = "DataHub did not return an incident count or incident rows."
            limit = "No incident conclusion is safe because the incident signal was unavailable."
        elif int(open_count or 0) == 0:
            status = "no_open_incident"
            finding = "DataHub returned zero open incidents and no incident row."
            limit = None
        else:
            status = "open_incident_details_unavailable"
            finding = f"DataHub reports {open_count} open incident(s), but did not return their details."
            limit = "The open incident count is known, but its failing fact and owner cannot be identified from this response."
        return {
            "status": status,
            "asset": asset,
            "finding": finding,
            "incident_count": open_count,
            "lineage_path": [asset] if asset else [],
            "upstream_candidates": upstream_names,
            "root_cause": None,
            "evidence_limit": limit,
            "next_step": "Query the incident details and upstream lineage before allowing an autonomous action." if status != "no_open_incident" else "Continue monitoring the asset.",
        }
    open_incidents = [row for row in incidents if str(row.get("status", "OPEN")).upper() not in {"RESOLVED", "CLOSED", "FIXED"}]
    incident = open_incidents[0] if open_incidents else incidents[0]
    signal = incident.get("signal") or incident.get("evidence_kind") or incident.get("type") or "incidents"
    failing = incident.get("message") or incident.get("description") or incident.get("result") or "Open incident reported by DataHub."
    source = incident.get("source") or incident.get("source_urn") or incident.get("platform") or "DataHub incident record"
    root = incident.get("entity_urn") or incident.get("entity") or (upstream_names[0] if upstream_names else asset)
    if isinstance(root, dict):
        root = root.get("urn") or root.get("entity_urn")
    path = [asset] if asset else []
    if root and root not in path:
        path.append(root)
    return {
        "status": "investigation_required" if open_incidents else "incident_details_resolved",
        "asset": asset,
        "finding": failing,
        "incident_count": open_count if open_count is not None else len(open_incidents),
        "root_cause": {
            "asset": root,
            "signal": signal,
            "fact": failing,
            "source": source,
            "status": incident.get("status") or "OPEN",
            "observed_at": incident.get("observed_at") or incident.get("timestamp") or incident.get("created_at"),
            "incident_urn": incident.get("urn") or incident.get("incident_urn"),
        },
        "lineage_path": path[: max(1, max_depth + 1)],
        "upstream_candidates": candidates,
        "evidence_limit": None if root else "The incident was returned but did not identify an entity or lineage root.",
        "next_step": f"Repair or acknowledge {signal} on {root or asset}, then poll DataHub and re-evaluate.",
    }
