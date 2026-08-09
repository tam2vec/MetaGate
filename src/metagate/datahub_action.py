"""Deployment-neutral DataHub Action adapter for MetaGate preflight.

DataHub deployments register webhooks/actions differently. This module keeps
the action contract stable while the deployment-specific registration remains
in ``examples/datahub-native-plugin``.
"""

from __future__ import annotations

from typing import Any, Callable


ACTION_NAME = "metagate.preflight"
CONTRACT_VERSION = "metagate.ai-context-contract/v1"


def native_action_metadata() -> dict[str, Any]:
    """Return the metadata a DataHub Action/webhook registration can expose."""
    return {
        "name": ACTION_NAME,
        "event": "dataset.preflight.requested",
        "mode": "fail-closed",
        "read_only_by_default": True,
        "contract_version": CONTRACT_VERSION,
    }


def validate_action_request(payload: dict[str, Any]) -> tuple[str, str]:
    """Extract and validate the two required fields from an action event."""
    urn = str(payload.get("entityUrn") or payload.get("urn") or "").strip()
    capability = str(payload.get("capability") or payload.get("action") or "").strip()
    if not urn:
        raise ValueError("entityUrn is required")
    if not capability:
        raise ValueError("capability is required")
    return urn, capability


def handle_action(
    payload: dict[str, Any],
    evaluator: Callable[[str, str], dict[str, Any]],
) -> dict[str, Any]:
    """Evaluate an action event and return the agent-facing contract.

    The returned contract is intentionally compact and contains no raw rows.
    A caller that wants to execute a tool must pass this contract to
    ``metagate.agent_gate.guarded_tool_call``.
    """
    urn, capability = validate_action_request(payload)
    result = evaluator(urn, capability)
    contract = result.get("constraint_contract") or {}
    return {
        "status": "ok",
        "action": ACTION_NAME,
        "entityUrn": urn,
        "capability": capability,
        "decision": result.get("effective_decision") or result.get("decision"),
        "allowed": bool(result.get("effective_allowed", result.get("allowed", False))),
        "decision_id": result.get("decision_id"),
        "evaluated_at": result.get("evaluated_at"),
        "contract_version": contract.get("contract_version", CONTRACT_VERSION),
        "constraint_contract": contract,
        "evidence": result.get("facts") or result.get("evidence", []),
        # Keep the agent contract readable. ``failed`` contains implementation
        # terms such as ``freshness.present``; the contract has the precise
        # reason a steward should see and the machine-readable failed terms.
        "blocking_reasons": contract.get("blocking_reasons") or result.get("blocking_reasons") or result.get("failed") or [],
        "failed_terms": result.get("failed") or contract.get("failed_terms") or [],
        "writeback": "read_only",
    }
