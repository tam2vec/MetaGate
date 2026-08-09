"""Fail-closed tool boundary for agents using MetaGate decisions.

The review page is a human explanation. This module is the enforcement point:
call it immediately before a tool or connector is invoked. A blocked contract
raises instead of returning a soft warning that an agent could ignore.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class ToolCallDenied(PermissionError):
    decision_id: str | None
    action: str
    reason: str
    contract: dict[str, Any]

    def __str__(self) -> str:
        return f"MetaGate blocked {self.action}: {self.reason}"


def authorize_tool_call(
    contract: dict[str, Any],
    *,
    action: str,
    dataset_urn: str,
    columns: list[str] | None = None,
    human_approval: str | None = None,
    tool_urn: str | None = None,
    service_urn: str | None = None,
) -> dict[str, Any]:
    """Validate scope and approval before a tool call is allowed."""
    decision_id = contract.get("decision_id")
    if contract.get("decision") != "allowed" or not contract.get("allowed_action"):
        raise ToolCallDenied(
            decision_id,
            action,
            "; ".join(contract.get("blocking_reasons") or ["No allowed action is present in the contract."]),
            contract,
        )
    if contract.get("allowed_action") != action:
        raise ToolCallDenied(decision_id, action, f"The contract authorizes {contract.get('allowed_action')}, not {action}.", contract)
    registry = contract.get("registry_evidence") or {}
    if contract.get("registry_required") and registry.get("status") != "verified":
        raise ToolCallDenied(
            decision_id,
            action,
            "; ".join(registry.get("blocking_reasons") or ["The agent, tool, and service chain was not verified."]),
            contract,
        )
    expected = contract.get("agent_context") or {}
    if tool_urn and expected.get("tool_urn") and tool_urn != expected.get("tool_urn"):
        raise ToolCallDenied(decision_id, action, "The requested tool is outside the verified agent contract.", contract)
    if service_urn and expected.get("service_urn") and service_urn != expected.get("service_urn"):
        raise ToolCallDenied(decision_id, action, "The requested service is outside the verified agent contract.", contract)
    if dataset_urn not in (contract.get("permitted_datasets") or []):
        raise ToolCallDenied(decision_id, action, "The dataset is outside the permitted contract scope.", contract)
    required_approval = bool(contract.get("required_human_approval"))
    if required_approval and not human_approval:
        raise ToolCallDenied(decision_id, action, "A named human approval is required before this action can run.", contract)
    permitted_columns = contract.get("permitted_columns") or []
    if columns and permitted_columns and not set(columns).issubset(set(permitted_columns)):
        denied = sorted(set(columns) - set(permitted_columns))
        raise ToolCallDenied(decision_id, action, f"Columns outside the permitted scope: {', '.join(denied)}.", contract)
    return {
        "authorized": True,
        "decision_id": decision_id,
        "action": action,
        "dataset_urn": dataset_urn,
        "human_approval": human_approval,
        "tool_urn": tool_urn or expected.get("tool_urn"),
        "service_urn": service_urn or expected.get("service_urn"),
    }


def guarded_tool_call(
    contract: dict[str, Any],
    *,
    action: str,
    dataset_urn: str,
    tool: Callable[..., Any],
    tool_kwargs: dict[str, Any] | None = None,
    columns: list[str] | None = None,
    human_approval: str | None = None,
    tool_urn: str | None = None,
    service_urn: str | None = None,
) -> Any:
    """Authorize then invoke a real callable; denial prevents invocation."""
    authorize_tool_call(
        contract,
        action=action,
        dataset_urn=dataset_urn,
        columns=columns,
        human_approval=human_approval,
        tool_urn=tool_urn,
        service_urn=service_urn,
    )
    return tool(**(tool_kwargs or {}))
