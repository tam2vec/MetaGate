"""Run the four-action Predicate enforcement story for a demo or CI job."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

from context_gradient.cli import _action_predicate
from context_gradient.datahub.adapter import DataHubEvidenceExtractor, GraphQLDataHubClient
from context_gradient.datahub.mock_client import FileDataHubClient
from context_gradient.sdk.admission import enforce_action_guardrails
from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.policy import load_policy
from predicate.contracts import build_constraint_contract
from context_gradient.skill import certify as skill_certify
from predicate.mcp_server import PredicateMCP


# The default story uses an asset with a deliberate quality gap. That makes
# the four gates visibly different: explanation can proceed, while higher-risk
# actions are stopped for the missing assertion/lineage evidence.
DEFAULT_URN = "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)"
ACTIONS = (
    "answer-business-questions",
    "generate-executive-metrics",
    "modify-dataset",
    "restricted-sql",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Show Predicate's action enforcement path.")
    parser.add_argument(
        "--urn",
        default=DEFAULT_URN,
        help=(
            "Dataset URN to evaluate. The default demonstrates the intended "
            "mixed result; use SampleHiveDataset for the complete-evidence "
            "allowed comparison."
        ),
    )
    parser.add_argument("--policy", default="examples/policies/enterprise_ai.yml")
    parser.add_argument("--datahub-file")
    parser.add_argument("--datahub-url")
    args = parser.parse_args()
    if args.datahub_file and args.datahub_url:
        parser.error("Use either --datahub-file or --datahub-url, not both.")
    if args.datahub_file:
        client = FileDataHubClient(args.datahub_file)
    elif args.datahub_url or os.environ.get("DATAHUB_GRAPHQL_URL"):
        client = GraphQLDataHubClient(args.datahub_url or os.environ.get("DATAHUB_GRAPHQL_URL"))
    else:
        client = FileDataHubClient("examples/data/six_asset_review_graph.json")
    policy = load_policy(args.policy)
    bundle = DataHubEvidenceExtractor(client).bundle(args.urn)
    certificate = ReadinessEngine(policy).certify(bundle).as_dict()
    evaluated_at = datetime.now(timezone.utc).isoformat()
    evaluations = []
    for action in ACTIONS:
        admission = enforce_action_guardrails(certificate, action).__dict__
        admission["action_predicate"] = _action_predicate(certificate, policy, action, admission["allowed"], admission.get("reason"))
        run = {
            **admission,
            "decision": "allowed" if admission["allowed"] else "blocked",
            "asset": args.urn.split(",")[-2] if "," in args.urn else args.urn,
            "urn": args.urn,
            "readiness_score": certificate.get("readiness_score"),
            "confidence": certificate.get("confidence"),
            "gaps": certificate.get("gaps", []),
            "score_trace": certificate.get("metadata", {}).get("score_trace", {}),
            "facts": certificate.get("metadata", {}).get("assessment", {}).get("facts", {}),
            "guidance": certificate.get("metadata", {}).get("assessment", {}).get("guidance", []),
            "datahub_observation": certificate.get("metadata", {}).get("datahub_observation", {}),
            "decision_id": f"pred-{int(datetime.now(timezone.utc).timestamp() * 1000)}-{action}",
            "evaluated_at": evaluated_at,
        }
        run["constraint_contract"] = build_constraint_contract(run, action)
        evaluations.append(run)
    # Exercise the two agent-facing surfaces in the same run. This is the
    # local proof that the Skill and MCP tools are not separate rule engines.
    source_file = args.datahub_file or (None if args.datahub_url else "examples/data/six_asset_review_graph.json")
    skill_result = skill_certify(
        args.urn,
        args.policy,
        datahub_url=args.datahub_url,
        datahub_file=source_file,
        capability="answer-business-questions",
    )
    mcp_result = PredicateMCP(args.policy, args.datahub_url, None, source_file).evaluate({
        "urn": args.urn,
        "capability": "answer-business-questions",
    })
    integration_proof = {
        "skill": {
            "entrypoint": "context_gradient.skill:certify",
            "decision": skill_result.get("decision"),
            "decision_id": skill_result.get("decision_id"),
            "contract_version": skill_result.get("constraint_contract", {}).get("contract_version"),
            "evidence_statuses": {
                key: value.get("status")
                for key, value in skill_result.get("constraint_contract", {}).get("evidence", {}).items()
                if isinstance(value, dict) and "status" in value
            },
        },
        "mcp": {
            "tool": "predicate_evaluate",
            "decision": mcp_result.get("decision"),
            "decision_id": mcp_result.get("decision_id"),
            "contract_version": mcp_result.get("constraint_contract", {}).get("contract_version"),
            "evidence_statuses": {
                key: value.get("status")
                for key, value in mcp_result.get("constraint_contract", {}).get("evidence", {}).items()
                if isinstance(value, dict) and "status" in value
            },
        },
        "same_asset": skill_result.get("entity_urn") == mcp_result.get("entity_urn") == args.urn,
        "same_decision": skill_result.get("decision") == mcp_result.get("decision"),
    }
    integration_proof["evidence_agreement"] = (
        integration_proof["skill"]["evidence_statuses"]
        == integration_proof["mcp"]["evidence_statuses"]
    )
    integration_proof["status"] = (
        "verified"
        if integration_proof["same_asset"]
        and integration_proof["same_decision"]
        and integration_proof["evidence_agreement"]
        else "attention_required"
    )
    integration_proof["official_datahub_mcp"] = {
        "status": "not_configured",
        "note": "Register the official DataHub MCP server separately to prove DataHub discovery in the demo."
    }
    decisions = [
        {
            "action": item["capability"],
            "decision": item["decision"],
            "readiness": item["readiness_score"],
            "confidence": item["confidence"],
            "reason": item.get("reason"),
            "decision_id": item["decision_id"],
        }
        for item in evaluations
    ]
    print(json.dumps({
        "story": "asset -> evidence -> action gate -> constrained agent",
        "asset": args.urn,
        "decisions": decisions,
        "constraint_contracts": [item["constraint_contract"] for item in evaluations],
        "integration_proof": integration_proof,
        "evaluations": evaluations,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
