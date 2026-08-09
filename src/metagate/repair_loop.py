"""Reusable repair, indexing-poll, re-evaluation, and audit sequence."""

from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any, Callable


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_repair_loop(
    before: dict[str, Any],
    *,
    repair: Callable[[], dict[str, Any]],
    poll: Callable[[int], dict[str, Any]],
    evaluate: Callable[[], dict[str, Any]],
    decision_id: str | None = None,
    max_attempts: int = 5,
    poll_interval: float = 0.0,
) -> dict[str, Any]:
    """Run one complete repair cycle and return a reproducible audit bundle."""
    urn = before.get("entity_urn") or before.get("urn")
    audit: list[dict[str, Any]] = []

    def event(event_type: str, payload: dict[str, Any]) -> None:
        audit.append({"event_type": event_type, "created_at": _now(), "payload": payload})

    before_gaps = before.get("failed") or before.get("gaps") or []
    event("before_evaluation", {"decision": before.get("decision"), "readiness": before.get("readiness_score", before.get("readiness")), "confidence": before.get("confidence"), "gaps": before_gaps})
    try:
        repair_result = repair() or {}
    except Exception as exc:
        repair_result = {"status": "error", "error": str(exc)}
    event("repair_applied", repair_result)
    if repair_result.get("status") == "error" or repair_result.get("applied") is False:
        return {
            "status": "repair_failed",
            "asset": urn,
            "decision_id": decision_id or before.get("decision_id"),
            "before": before,
            "repair": repair_result,
            "indexing": {"status": "not_started"},
            "after": None,
            "score_delta": None,
            "audit_events": audit,
        }
    observed = None
    readable = False
    poll_error = None
    source_observed_at = None
    for attempt in range(1, max(1, max_attempts) + 1):
        try:
            observed = poll(attempt) or {}
        except Exception as exc:
            observed = {"status": "error", "error": str(exc), "readable": False}
            poll_error = str(exc)
        event("indexing_poll", {"attempt": attempt, **observed})
        source_observed_at = observed.get("source_observed_at") or observed.get("observed_at") or source_observed_at
        if observed.get("readable") is True or observed.get("status") in {"ready", "visible", "success"}:
            readable = True
            break
        if attempt < max(1, max_attempts) and poll_interval > 0:
            time.sleep(poll_interval)
    indexing_status = "readable" if readable else "poll_timeout"
    if not readable and poll_error:
        indexing_status = "poll_error"
    after = evaluate()
    after_gaps = after.get("failed") or after.get("gaps") or []
    event("after_evaluation", {"decision": after.get("decision"), "readiness": after.get("readiness_score", after.get("readiness")), "confidence": after.get("confidence"), "gaps": after_gaps, "indexing_status": indexing_status})
    before_score = before.get("readiness_score", before.get("readiness"))
    after_score = after.get("readiness_score", after.get("readiness"))
    return {
        "status": "repaired" if readable and after.get("decision") == "allowed" else ("rechecked" if readable else indexing_status),
        "asset": urn,
        "decision_id": decision_id or after.get("decision_id") or before.get("decision_id"),
        "before": before,
        "repair": repair_result,
        "indexing": {**(observed or {}), "status": indexing_status, "attempts": max(1, max_attempts) if not readable else len([item for item in audit if item["event_type"] == "indexing_poll"]), "source_observed_at": source_observed_at},
        "after": after,
        "score_delta": round(float(after_score) - float(before_score), 2) if before_score is not None and after_score is not None else None,
        "before_gaps": before_gaps,
        "after_gaps": after_gaps,
        "audit_events": audit,
    }
