"""DataHub Skill-compatible entrypoint for MetaGate.

The Skill uses the same extractor and action guardrails as the CLI, review
server, and MetaGate MCP server.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from typing import Any

from context_gradient.datahub.adapter import DataHubEvidenceExtractor, DataHubWriteback, GraphQLDataHubClient
from context_gradient.datahub.mock_client import FileDataHubClient
from context_gradient.sdk.admission import enforce_action_guardrails
from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.policy import load_policy
from metagate.contracts import build_constraint_contract


DEFAULT_CAPABILITY = "autonomous-agent-action"


def _decision_payload(certificate: dict[str, Any], capability: str) -> dict[str, Any]:
    """Attach the shared MetaGate decision contract to a certificate."""
    decision = enforce_action_guardrails(certificate, capability)
    now = datetime.now(timezone.utc)
    decision_payload = {
        "entity_urn": decision.entity_urn,
        "capability": decision.capability,
        "allowed": decision.allowed,
        "decision": "allowed" if decision.allowed else "blocked",
        "reason": decision.reason,
        "evidence": decision.evidence,
        "escalation_owner": decision.escalation_owner,
        "decision_id": f"pred-{int(now.timestamp() * 1000)}",
        "evaluated_at": now.isoformat(),
        "facts": certificate.get("metadata", {}).get("assessment", {}).get("facts", {}),
        "guidance": certificate.get("recommendations", []),
        "score_trace": certificate.get("metadata", {}).get("score_trace", {}),
        "datahub_observation": certificate.get("metadata", {}).get("datahub_observation", {}),
        "gaps": certificate.get("gaps", []),
    }
    decision_payload["constraint_contract"] = build_constraint_contract(
        decision_payload,
        capability,
    )
    return decision_payload


def _certify(
    entity_urn: str,
    policy_path: str,
    datahub_url: str | None = None,
    datahub_file: str | None = None,
    capability: str = DEFAULT_CAPABILITY,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if datahub_file and datahub_url:
        raise ValueError("Use either datahub_file or datahub_url, not both")
    client = FileDataHubClient(datahub_file) if datahub_file else GraphQLDataHubClient(
        datahub_url, token=os.environ.get("DATAHUB_TOKEN")
    )
    bundle = DataHubEvidenceExtractor(client).bundle(entity_urn)
    certificate = ReadinessEngine(load_policy(policy_path)).certify(bundle).as_dict()
    return certificate, _decision_payload(certificate, capability)


def certify(
    entity_urn: str,
    policy_path: str,
    datahub_url: str | None = None,
    datahub_file: str | None = None,
    capability: str = DEFAULT_CAPABILITY,
) -> dict:
    """Return a certificate plus the evidence-backed action boundary."""
    certificate, decision = _certify(
        entity_urn,
        policy_path,
        datahub_url,
        datahub_file,
        capability,
    )
    certificate["requested_action"] = capability
    certificate["decision"] = decision["decision"]
    certificate["decision_id"] = decision["decision_id"]
    certificate["evaluated_at"] = decision["evaluated_at"]
    certificate["constraint_contract"] = decision["constraint_contract"]
    return certificate


def certify_and_write(
    entity_urn: str,
    policy_path: str,
    datahub_url: str | None = None,
    datahub_file: str | None = None,
    capability: str = DEFAULT_CAPABILITY,
) -> dict:
    """Certify and publish through deployment-configured DataHub mutations."""
    if datahub_file and datahub_url:
        raise ValueError("Use either datahub_file or datahub_url, not both")
    client = FileDataHubClient(datahub_file) if datahub_file else GraphQLDataHubClient(
        datahub_url, token=os.environ.get("DATAHUB_TOKEN")
    )
    bundle = DataHubEvidenceExtractor(client).bundle(entity_urn)
    payload = ReadinessEngine(load_policy(policy_path)).certify(bundle).as_dict()
    decision = _decision_payload(payload, capability)
    payload["requested_action"] = capability
    payload["decision"] = decision["decision"]
    payload["decision_id"] = decision["decision_id"]
    payload["evaluated_at"] = decision["evaluated_at"]
    payload["constraint_contract"] = decision["constraint_contract"]
    payload["writeback"] = DataHubWriteback(client).publish(entity_urn, payload)
    return payload


def main() -> None:
    """Small JSON CLI for Skill smoke tests and agent runners."""
    parser = argparse.ArgumentParser(prog="metagate-skill")
    parser.add_argument("urn", help="DataHub entity URN")
    parser.add_argument("--policy", required=True, help="YAML policy profile")
    parser.add_argument("--datahub-url", help="DataHub GraphQL endpoint")
    parser.add_argument("--datahub-file", help="Local DataHub-shaped graph for a safe smoke test")
    parser.add_argument("--capability", default=DEFAULT_CAPABILITY)
    parser.add_argument("--writeback", action="store_true")
    args = parser.parse_args()
    result = (
        certify_and_write(
            args.urn,
            args.policy,
            datahub_url=args.datahub_url,
            datahub_file=args.datahub_file,
            capability=args.capability,
        )
        if args.writeback
        else certify(
            args.urn,
            args.policy,
            datahub_url=args.datahub_url,
            datahub_file=args.datahub_file,
            capability=args.capability,
        )
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
