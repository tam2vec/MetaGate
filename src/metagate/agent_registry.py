"""Local adapter for DataHub Agent Registry and Service Catalog evidence.

DataHub's agent registry models agents, skills, tools, and the datasets an
agent consumes. Its service catalog models the service that owns an API or
MCP tool. MetaGate uses the same vocabulary so a decision can verify the
full execution path before an agent is allowed to act.

The catalog is intentionally JSON-backed for the local hackathon deployment.
The shape mirrors DataHub entities and can later be populated from the Cloud
or OSS APIs without changing the decision contract.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_AGENT_URN = "urn:li:aiAgent:metagate-review-agent"
DEFAULT_SKILL_URN = "urn:li:agentSkill:metagate-preflight"
DEFAULT_TOOL_URN = "urn:li:api:metagate.evaluate"
DEFAULT_SERVICE_URN = "urn:li:service:metagate-review-api"


def default_catalog() -> dict[str, Any]:
    """Return a small DataHub-shaped catalog for the local MetaGate API."""
    return {
        "catalog_version": "1.0",
        "source": "metagate-local-agent-registry",
        "agents": [{
            "urn": DEFAULT_AGENT_URN,
            "name": "MetaGate Review Agent",
            "description": "Requests governed AI action decisions from MetaGate.",
            "skills": [DEFAULT_SKILL_URN],
            "tools": [DEFAULT_TOOL_URN],
            "consumes_datasets": ["*"],
        }],
        "skills": [{
            "urn": DEFAULT_SKILL_URN,
            "name": "MetaGate Preflight",
            "description": "Checks current DataHub evidence before an agent uses a dataset.",
            "tools": [DEFAULT_TOOL_URN],
            "actions": [
                "answer-business-questions",
                "generate-executive-metrics",
                "autonomous-agent-action",
                "modify-dataset",
                "restricted-sql",
            ],
        }],
        "apis": [{
            "urn": DEFAULT_TOOL_URN,
            "name": "MetaGate evaluate",
            "subtype": "REST_ENDPOINT",
            "service": DEFAULT_SERVICE_URN,
            "path": "/api/evaluate",
            "method": "GET",
            "contract": {
                "input": ["urn", "capability"],
                "output": ["decision", "constraint_contract", "evidence", "decision_id"],
            },
        }],
        "services": [{
            "urn": DEFAULT_SERVICE_URN,
            "name": "MetaGate Review API",
            "subtype": "REST",
            "apis": [DEFAULT_TOOL_URN],
            "base_url": "http://127.0.0.1:8765",
        }],
    }


def load_catalog(path: str | Path | None = None) -> dict[str, Any]:
    if not path:
        return default_catalog()
    source = Path(path)
    return json.loads(source.read_text(encoding="utf-8"))


def _index(catalog: dict[str, Any], key: str) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("urn")): item
        for item in catalog.get(key, [])
        if isinstance(item, dict) and item.get("urn")
    }


def _requested(value: str | None, default: str) -> str:
    return str(value or default)


def resolve_agent_context(
    *,
    registry_path: str | Path | None = None,
    dataset_urn: str | None = None,
    agent_id: str | None = None,
    skill_id: str | None = None,
    tool_id: str | None = None,
    service_id: str | None = None,
    requested: bool = False,
    capability: str | None = None,
) -> dict[str, Any]:
    """Verify agent -> skill -> tool -> service scope for one request."""
    explicit = requested or any(value for value in (registry_path, agent_id, skill_id, tool_id, service_id))
    if not explicit:
        return {
            "status": "not_requested",
            "source": "agent-registry-not-configured",
            "blocking_reasons": [],
            "evidence": [],
        }
    try:
        catalog = load_catalog(registry_path)
    except (OSError, ValueError, TypeError) as exc:
        return {
            "status": "unavailable",
            "source": str(registry_path or "default catalog"),
            "blocking_reasons": [f"Agent Registry/Service Catalog could not be read: {exc}"],
            "evidence": [],
        }

    agents = _index(catalog, "agents")
    skills = _index(catalog, "skills")
    apis = _index(catalog, "apis")
    services = _index(catalog, "services")
    ids = {
        "agent_urn": _requested(agent_id, DEFAULT_AGENT_URN),
        "skill_urn": _requested(skill_id, DEFAULT_SKILL_URN),
        "tool_urn": _requested(tool_id, DEFAULT_TOOL_URN),
        "service_urn": _requested(service_id, DEFAULT_SERVICE_URN),
    }
    agent = agents.get(ids["agent_urn"])
    skill = skills.get(ids["skill_urn"])
    tool = apis.get(ids["tool_urn"])
    service = services.get(ids["service_urn"])
    reasons: list[str] = []
    checks: list[dict[str, Any]] = []

    def require(value: dict[str, Any] | None, kind: str, urn: str) -> None:
        if value is None:
            reasons.append(f"{kind} {urn} is not registered.")
            checks.append({"check": f"{kind}.present", "result": False})
        else:
            checks.append({"check": f"{kind}.present", "result": True})

    require(agent, "agent", ids["agent_urn"])
    require(skill, "skill", ids["skill_urn"])
    require(tool, "tool", ids["tool_urn"])
    require(service, "service", ids["service_urn"])

    if agent and ids["skill_urn"] not in (agent.get("skills") or []):
        reasons.append("The registered agent is not linked to the requested skill.")
        checks.append({"check": "agent.skill_link", "result": False})
    if agent and ids["tool_urn"] not in (agent.get("tools") or []):
        reasons.append("The registered agent is not linked to the requested tool.")
        checks.append({"check": "agent.tool_link", "result": False})
    if skill and ids["tool_urn"] not in (skill.get("tools") or []):
        reasons.append("The registered skill is not linked to the requested tool.")
        checks.append({"check": "skill.tool_link", "result": False})
    if skill:
        allowed_actions = skill.get("actions") or []
        if allowed_actions and capability and capability not in allowed_actions:
            reasons.append(f"The registered skill does not authorize the requested capability: {capability}.")
            checks.append({"check": "skill.capability_scope", "result": False, "capability": capability})
        elif allowed_actions and capability:
            checks.append({"check": "skill.capability_scope", "result": True, "capability": capability})
    if tool and tool.get("service") != ids["service_urn"]:
        reasons.append("The requested tool is owned by a different service.")
        checks.append({"check": "tool.service_link", "result": False})
    if service and ids["tool_urn"] not in (service.get("apis") or []):
        reasons.append("The service does not advertise the requested tool.")
        checks.append({"check": "service.tool_link", "result": False})
    if agent and dataset_urn:
        datasets = agent.get("consumes_datasets") or []
        if "*" not in datasets and dataset_urn not in datasets:
            reasons.append("The registered agent is not permitted to consume this dataset.")
            checks.append({"check": "agent.dataset_scope", "result": False})
        else:
            checks.append({"check": "agent.dataset_scope", "result": True})

    status = "verified" if not reasons else "scope_mismatch"
    evidence = [
        f"agent {ids['agent_urn']} registered",
        f"skill {ids['skill_urn']} registered",
        f"tool {ids['tool_urn']} registered as {tool.get('subtype', 'unknown') if tool else 'unknown'}",
        f"service {ids['service_urn']} registered as {service.get('subtype', 'unknown') if service else 'unknown'}",
    ]
    return {
        "status": status,
        "source": str(registry_path or "metagate-local-agent-registry"),
        **ids,
        "agent_name": agent.get("name") if agent else None,
        "skill_name": skill.get("name") if skill else None,
        "tool_name": tool.get("name") if tool else None,
        "service_name": service.get("name") if service else None,
        "tool_subtype": tool.get("subtype") if tool else None,
        "service_subtype": service.get("subtype") if service else None,
        "tool_contract": tool.get("contract") if tool else {},
        "skill_actions": list(skill.get("actions") or []) if skill else [],
        "requested_capability": capability,
        "checks": checks,
        "blocking_reasons": list(dict.fromkeys(reasons)),
        "evidence": evidence if not reasons else evidence + list(dict.fromkeys(reasons)),
    }


def apply_agent_registry_gate(
    decision: dict[str, Any],
    context: dict[str, Any],
    capability: str,
) -> dict[str, Any]:
    """Mutate an action decision to blocked when its execution chain is unsafe."""
    decision["agent_context"] = context
    decision["registry_evidence"] = context
    if context.get("status") == "verified":
        return decision
    reasons = list(context.get("blocking_reasons") or ["Agent Registry and Service Catalog evidence was not verified."])
    decision["allowed"] = False
    decision["decision"] = "blocked"
    decision["reason"] = "; ".join(dict.fromkeys([str(decision.get("reason") or "")] + reasons)).strip("; ")
    metagate = decision.get("action_metagate")
    if isinstance(metagate, dict):
        metagate["result"] = False
        metagate["decision"] = "blocked"
        metagate.setdefault("failed_terms", []).append("agent_registry.verified")
        metagate.setdefault("reasons", []).extend(reasons)
    return decision
