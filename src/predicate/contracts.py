"""Build the compact enforcement contract returned to an agent.

Scores are useful for humans, but an agent needs an explicit boundary: what it
may do, what it may not do, and which current facts justify that boundary.
This module deliberately consumes the existing review-run shape so the CLI,
review server, and MCP server cannot drift into different interpretations.
"""

from __future__ import annotations

from typing import Any


ACTION_CATALOG = (
    "answer-business-questions",
    "generate-executive-metrics",
    "autonomous-agent-action",
    "modify-dataset",
    "restricted-sql",
)

HIGH_RISK_ACTIONS = {"generate-executive-metrics", "autonomous-agent-action", "modify-dataset", "restricted-sql"}


def _rows(run: dict[str, Any]) -> list[dict[str, Any]]:
    trace = run.get("score_trace") or {}
    value = trace.get("evidence") if isinstance(trace, dict) else []
    if not value:
        return []
    if isinstance(value, dict):
        value = list(value.values())
    return [item for item in value if isinstance(item, dict)]


def _row(rows: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    return next((item for item in rows if item.get("kind") == kind or item.get("evidence_kind") == kind), {})


def _status(item: dict[str, Any]) -> str:
    if not item:
        return "unavailable"
    if item.get("available") is False or item.get("state") == "unavailable":
        return "unavailable"
    if item.get("state") in {"stale", "contradictory", "incomplete", "open_incident"}:
        return str(item["state"])
    if item.get("present") is False or item.get("state") in {"missing", "absent"}:
        return "absent"
    return "present"


def _evidence_status(
    kind: str,
    item: dict[str, Any],
    facts: dict[str, Any],
    *,
    assertion_rows: list[dict[str, Any]] | None = None,
) -> str:
    """Translate raw evidence into a truthful, human-readable status.

    The evaluator may know that a signal exists without being able to verify
    the fact required by a policy.  Keeping those states separate prevents a
    failed assertion, a missing assertion run, and a GraphQL error from
    looking identical in the agent contract.
    """
    base = _status(item)
    if base in {"unavailable", "absent", "stale", "contradictory", "incomplete", "open_incident"}:
        return base
    value = facts.get(kind) if isinstance(facts.get(kind), dict) else {}
    if kind == "assertions":
        rows = assertion_rows or []
        if not rows or value.get("incomplete") or value.get("missing_results"):
            return "incomplete"
    elif kind == "freshness":
        if not value.get("timestamp") and not value.get("observed_at"):
            return "incomplete"
    elif kind == "incidents":
        open_count = value.get("open", value.get("open_count"))
        if open_count is None:
            return "unavailable"
        return "open" if int(open_count or 0) > 0 else "clear"
    elif kind == "lineage":
        coverage = value.get("coverage")
        if isinstance(coverage, (int, float)):
            return "complete" if coverage >= 1 else "partial"
    elif kind == "column_lineage":
        mapped = value.get("mapped", value.get("mapped_count", value.get("mapping_count")))
        total = value.get("total", value.get("column_count"))
        if isinstance(mapped, (int, float)) and isinstance(total, (int, float)):
            return "complete" if total == 0 or mapped >= total else "partial"
    elif kind == "glossary":
        if not value.get("terms"):
            return "absent"
    return base


def _assertion_result_state(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "unavailable"
    statuses = {str(item.get("status") or item.get("result") or item.get("type") or "").upper() for item in rows}
    if any(value in {"FAIL", "FAILURE", "ERROR", "FAILED", "UNKNOWN"} for value in statuses):
        return "failing"
    if all(value in {"PASS", "PASSED", "SUCCESS", "SUCCEEDED", "OK"} for value in statuses):
        return "passing"
    return "unknown"


def _facts(run: dict[str, Any]) -> dict[str, Any]:
    facts = run.get("facts") or {}
    return facts if isinstance(facts, dict) else {}


def _compact_evidence(run: dict[str, Any]) -> dict[str, Any]:
    rows = _rows(run)
    facts = _facts(run)
    assertions = facts.get("assertions") if isinstance(facts.get("assertions"), dict) else {}
    freshness = facts.get("freshness") if isinstance(facts.get("freshness"), dict) else {}
    lineage = facts.get("lineage") if isinstance(facts.get("lineage"), dict) else {}
    columns = facts.get("column_lineage") if isinstance(facts.get("column_lineage"), dict) else {}
    glossary_terms = facts.get("glossary_terms") or []
    owner = facts.get("owner")
    incidents = facts.get("incidents") if isinstance(facts.get("incidents"), dict) else {}

    assertion_rows = assertions.get("latest_results") or assertions.get("results") or []
    if isinstance(assertion_rows, dict):
        assertion_rows = [assertion_rows]
    latest_by_name: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(assertion_rows if isinstance(assertion_rows, list) else []):
        if not isinstance(item, dict):
            continue
        key = str(item.get("assertion_urn") or item.get("assertion_name") or item.get("name") or item.get("urn") or index)
        current = latest_by_name.get(key)
        if current is None or _observation_key(item) >= _observation_key(current):
            latest_by_name[key] = item
    assertion_rows = list(latest_by_name.values())
    latest_assertion = max(assertion_rows, key=_observation_key) if assertion_rows else None
    assertion_row = _row(rows, "assertions")
    freshness_row = _row(rows, "freshness")
    ownership_row = _row(rows, "ownership")
    lineage_row = _row(rows, "lineage")
    column_lineage_row = _row(rows, "column_lineage")
    glossary_row = _row(rows, "glossary")
    incidents_row = _row(rows, "incidents")
    return {
        "assertions": {
            "status": _evidence_status("assertions", assertion_row, facts, assertion_rows=assertion_rows),
            "result_state": _assertion_result_state(assertion_rows),
            "count": assertions.get("count", assertions.get("total")),
            "passed": assertions.get("passed", assertions.get("passing")),
            "failed": assertions.get("failed", assertions.get("failing")),
            "latest_result": latest_assertion,
            "latest_results": assertion_rows,
            "observed_at": assertion_row.get("observed_at"),
        },
        "freshness": {
            "status": _evidence_status("freshness", freshness_row, facts),
            "timestamp": freshness.get("timestamp", freshness.get("observed_at")),
            "sla": freshness.get("sla", freshness.get("max_age_minutes")),
            "observed_at": freshness_row.get("observed_at"),
        },
        "owner": {
            "status": _evidence_status("ownership", ownership_row, facts),
            "value": owner,
            "observed_at": ownership_row.get("observed_at"),
        },
        "lineage": {
            "status": _evidence_status("lineage", lineage_row, facts),
            "upstream": lineage.get("upstream", lineage.get("upstream_count")),
            "downstream": lineage.get("downstream", lineage.get("downstream_count")),
            "coverage": lineage.get("coverage", 1.0 if lineage.get("upstream_count", 0) or lineage.get("downstream_count", 0) else 0.0),
            "observed_at": lineage_row.get("observed_at"),
        },
        "column_lineage": {
            "status": _evidence_status("column_lineage", column_lineage_row, facts),
            "mapped": columns.get("mapped", columns.get("mapped_count", columns.get("mapping_count"))),
            "total": columns.get("total", columns.get("column_count")),
            "missing": columns.get("missing", columns.get("missing_columns", [])),
            "observed_at": column_lineage_row.get("observed_at"),
        },
        "glossary": {
            "terms": glossary_terms,
            "status": _evidence_status("glossary", glossary_row, {**facts, "glossary": {"terms": glossary_terms}}),
            "observed_at": glossary_row.get("observed_at"),
        },
        "incidents": {
            "status": _evidence_status("incidents", incidents_row, facts),
            "open": incidents.get("open", incidents.get("open_count")),
            "observed_at": incidents_row.get("observed_at"),
        },
    }


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _observation_key(item: dict[str, Any]) -> tuple:
    value = item.get("observed_at") or item.get("timestamp") or item.get("timestampMillis") or item.get("created_at") or ""
    try:
        return (0, int(value))
    except (TypeError, ValueError):
        return (1, str(value))


def build_constraint_contract(run: dict[str, Any], capability: str | None = None) -> dict[str, Any]:
    """Return a conservative, evidence-first boundary for one decision."""
    capability = capability or str(run.get("capability") or "autonomous-agent-action")
    urn = str(run.get("entity_urn") or run.get("urn") or "")
    decision = str(run.get("effective_decision") or run.get("decision") or "unavailable")
    allowed = bool(run.get("effective_allowed", run.get("allowed", decision == "allowed"))) and decision == "allowed"
    trace = run.get("score_trace") or {}
    coverage = trace.get("evidence_coverage", {}) if isinstance(trace, dict) else {}
    gaps = run.get("gaps") or []
    failed_terms = run.get("failed_terms") or []
    decision_reason = str(run.get("reason") or "")
    reasons = ([decision_reason] if not allowed and decision_reason else [])
    reasons += [str(value) for value in failed_terms]
    reasons += [str(item.get("message") or item.get("recommendation") or "") for item in gaps if isinstance(item, dict)]
    forbidden = list(ACTION_CATALOG) if not allowed else [item for item in ACTION_CATALOG if item != capability]
    facts = _facts(run)
    columns = facts.get("column_lineage") if isinstance(facts.get("column_lineage"), dict) else {}
    permitted_columns = columns.get("mapped_column_names") or columns.get("columns") or []
    if not isinstance(permitted_columns, list):
        permitted_columns = []
    guidance = run.get("guidance") or run.get("recommendations") or []
    next_step = guidance[0] if isinstance(guidance, list) and guidance else ("Ask a steward to repair the blocking evidence, then re-check." if not allowed else "Use the certificate within the approved agent flow.")

    if allowed and capability in HIGH_RISK_ACTIONS:
        approval_reason = "This is a high-impact action; a designated steward must approve it before execution."
    elif allowed:
        approval_reason = None
    else:
        approval_reason = "A steward must repair or verify the blocking evidence before this action can run."

    return {
        "contract_version": "1.0",
        "decision_id": run.get("decision_id"),
        "evaluated_at": run.get("evaluated_at") or run.get("generated_at"),
        "asset": urn,
        "action": capability,
        "decision": decision,
        "allowed_action": capability if allowed else None,
        "forbidden_actions": forbidden,
        "required_human_approval": not allowed or capability in HIGH_RISK_ACTIONS,
        "approval_reason": approval_reason,
        "permitted_datasets": [urn] if allowed else [],
        "permitted_columns": permitted_columns,
        "evidence": _compact_evidence(run),
        "evidence_used": run.get("evidence") or run.get("verified_claims") or [],
        "unavailable_evidence": coverage.get("unavailable", []),
        "absent_evidence": coverage.get("confirmed_absent", []),
        "blocking_reasons": _dedupe(reasons) if not allowed else [],
        "decision_basis": decision_reason or ("Capability is certified by the active policy." if allowed else "No verified decision was available."),
        "next_step": next_step,
        "source_observation": run.get("datahub_observation") or run.get("observation") or {},
    }
