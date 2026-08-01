"""Run a read-only Predicate validation against a private DataHub deployment."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

from context_gradient.datahub.adapter import DataHubEvidenceExtractor, GraphQLDataHubClient
from context_gradient.sdk.admission import admit_capability
from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.policy import load_policy


DEFAULT_URNS = [
    "urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.customer_lifetime_value,PROD)",
    "urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.revenue,PROD)",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only Predicate validation for a private DataHub deployment."
    )
    parser.add_argument("--datahub-url", default=os.environ.get("DATAHUB_GRAPHQL_URL"), required=not os.environ.get("DATAHUB_GRAPHQL_URL"))
    parser.add_argument("--policy", default="examples/policies/finance-production.yml")
    parser.add_argument("--capability", default="autonomous-agent-action")
    parser.add_argument("--urn", action="append", dest="urns", help="DataHub URN; repeat for multiple assets")
    args = parser.parse_args()

    client = GraphQLDataHubClient(args.datahub_url, token=os.environ.get("DATAHUB_TOKEN"))
    extractor = DataHubEvidenceExtractor(client)
    engine = ReadinessEngine(load_policy(args.policy))
    results = []
    for urn in args.urns or DEFAULT_URNS:
        bundle = extractor.bundle(urn)
        certificate = engine.certify(bundle).as_dict()
        decision = admit_capability(certificate, args.capability).__dict__
        results.append(
            {
                "asset": urn,
                "decision": "allowed" if decision["allowed"] else "blocked",
                "allowed": decision["allowed"],
                "readiness": certificate.get("readiness_score"),
                "confidence": certificate.get("confidence"),
                "evidence_signals": len(certificate.get("evidence", [])),
                "reason": decision["reason"],
            }
        )

    print(json.dumps({
        "product": "Predicate",
        "mode": "private-datahub-read-only",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "datahub_url_configured": True,
        "token_present": bool(os.environ.get("DATAHUB_TOKEN")),
        "policy": args.policy,
        "capability": args.capability,
        "results": results,
    }, indent=2))


if __name__ == "__main__":
    main()
