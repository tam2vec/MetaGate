"""Run a read-only MetaGate validation against a private DataHub deployment."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

from context_gradient.datahub.adapter import DataHubEvidenceExtractor, GraphQLDataHubClient
from context_gradient.sdk.admission import enforce_action_guardrails
from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.policy import load_policy


DEFAULT_URNS = [
    "urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.customer_lifetime_value,PROD)",
    "urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.revenue,PROD)",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only MetaGate validation for a private DataHub deployment."
    )
    parser.add_argument("--datahub-url", default=os.environ.get("DATAHUB_GRAPHQL_URL"), required=not os.environ.get("DATAHUB_GRAPHQL_URL"))
    parser.add_argument("--policy", default="examples/policies/finance-production.yml")
    parser.add_argument("--capability", default="autonomous-agent-action")
    parser.add_argument("--urn", action="append", dest="urns", help="DataHub URN; repeat for multiple assets")
    parser.add_argument(
        "--fail-on-unavailable",
        action="store_true",
        help="Exit non-zero when DataHub does not expose an evidence surface.",
    )
    parser.add_argument(
        "--fail-on-error",
        action="store_true",
        help="Exit non-zero when any requested asset cannot be evaluated.",
    )
    args = parser.parse_args()

    client = GraphQLDataHubClient(args.datahub_url, token=os.environ.get("DATAHUB_TOKEN"))
    extractor = DataHubEvidenceExtractor(client)
    engine = ReadinessEngine(load_policy(args.policy))
    results = []
    for urn in args.urns or DEFAULT_URNS:
        try:
            bundle = extractor.bundle(urn)
            certificate = engine.certify(bundle).as_dict()
            decision = enforce_action_guardrails(certificate, args.capability).__dict__
            observation = certificate.get("metadata", {}).get("datahub_observation", {})
            results.append(
                {
                    "asset": urn,
                    "status": "evaluated",
                    "decision": "allowed" if decision["allowed"] else "blocked",
                    "allowed": decision["allowed"],
                    "readiness": certificate.get("readiness_score"),
                    "confidence": certificate.get("confidence"),
                    "evidence_signals": len(certificate.get("evidence", [])),
                    "available_evidence": observation.get("available_evidence", []),
                    "unavailable_evidence": observation.get("unavailable_evidence", {}),
                    "score_trace": certificate.get("metadata", {}).get("score_trace", {}),
                    "reason": decision["reason"],
                }
            )
        except Exception as error:
            results.append({"asset": urn, "status": "error", "error": str(error)})

    report = {
        "product": "MetaGate",
        "mode": "private-datahub-read-only",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "datahub_url_configured": True,
        "token_present": bool(os.environ.get("DATAHUB_TOKEN")),
        "policy": args.policy,
        "capability": args.capability,
        "results": results,
    }
    print(json.dumps(report, indent=2))
    if args.fail_on_unavailable and any(result.get("unavailable_evidence") for result in results):
        raise SystemExit(2)
    if args.fail_on_error and any(result.get("status") == "error" for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
