"""A transparent repair-loop proof used by the local review surface.

This is intentionally a fixture proof. The real DataHub mutation path lives in
``scripts/writeback_datahub.py`` and is only enabled with an explicit token and
deployment-approved write contract.
"""

from __future__ import annotations

from typing import Any

from metagate.repair_loop import run_repair_loop


def run_fixture_repair_proof() -> dict[str, Any]:
    """Show repair, indexing visibility, re-check, and audit in one result."""
    before = {
        "entity_urn": "urn:li:dataset:(urn:li:dataPlatform:hive,repair-demo,PROD)",
        "decision": "blocked",
        "readiness": 71.4,
        "confidence": 68.1,
        "failed": ["freshness.present"],
    }
    state = {"visible": False, "repair_applied": False}

    def repair() -> dict[str, Any]:
        state["repair_applied"] = True
        return {
            "status": "applied",
            "applied": True,
            "transport": "fixture-demo",
            "simulation": True,
            "changed": ["freshness.timestamp", "freshness.sla"],
            "exact_repair": "refresh the source and publish a timestamp inside the policy SLA",
        }

    def poll(attempt: int) -> dict[str, Any]:
        if attempt < 2:
            return {"status": "waiting", "readable": False, "attempt": attempt}
        state["visible"] = True
        return {
            "status": "ready",
            "readable": True,
            "attempt": attempt,
            "source_observed_at": "fixture-demo-after-repair",
        }

    def evaluate() -> dict[str, Any]:
        visible = state["visible"] and state["repair_applied"]
        return {
            "decision": "allowed" if visible else "blocked",
            "readiness": 96.2 if visible else 71.4,
            "confidence": 94.8 if visible else 68.1,
            "failed": [] if visible else ["freshness.present"],
            "decision_id": "pred-repair-demo-after",
        }

    result = run_repair_loop(
        before,
        repair=repair,
        poll=poll,
        evaluate=evaluate,
        decision_id="pred-repair-demo-before",
    )
    result["transport"] = "fixture-demo"
    result["simulation"] = True
    result["proof_note"] = (
        "This proof demonstrates sequencing only. It did not mutate DataHub. "
        "Use scripts/writeback_datahub.py for an authorized local write-back."
    )
    return result
