"""Evaluate one asset and write/read back its Predicate contract through GraphQL."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from context_gradient.cli import _action_predicate
from context_gradient.datahub.adapter import DataHubEvidenceExtractor, DataHubWriteback, GraphQLDataHubClient
from context_gradient.sdk.admission import admit_capability
from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.policy import load_policy


def main() -> None:
    parser = argparse.ArgumentParser(description="Predicate DataHub write-back with read-after-write verification.")
    parser.add_argument("urn")
    parser.add_argument("--policy", required=True)
    parser.add_argument("--datahub-url", default=os.environ.get("DATAHUB_GRAPHQL_URL"), required=not os.environ.get("DATAHUB_GRAPHQL_URL"))
    parser.add_argument("--capability", default="autonomous-agent-action")
    parser.add_argument("--mutation-file", required=True, help="Deployment-approved GraphQL mutation document")
    parser.add_argument("--verify-query-file", required=True, help="GraphQL query that returns the written contract")
    parser.add_argument("--yes", action="store_true", help="Confirm this is a non-production write-back test")
    args = parser.parse_args()
    if not args.yes:
        parser.error("Add --yes only after confirming this targets a non-production namespace.")

    os.environ["DATAHUB_CERTIFICATE_MUTATION"] = Path(args.mutation_file).read_text()
    os.environ["DATAHUB_CERTIFICATE_QUERY"] = Path(args.verify_query_file).read_text()
    client = GraphQLDataHubClient(args.datahub_url, token=os.environ.get("DATAHUB_TOKEN"))
    policy = load_policy(args.policy)
    certificate = ReadinessEngine(policy).certify(DataHubEvidenceExtractor(client).bundle(args.urn)).as_dict()
    decision = admit_capability(certificate, args.capability).__dict__
    decision["action_predicate"] = _action_predicate(certificate, policy, args.capability, decision["allowed"])
    certificate["predicate_decision"] = decision["action_predicate"]
    receipt = DataHubWriteback(client).publish(args.urn, certificate)
    print(json.dumps({"product": "Predicate", "writeback": receipt, "decision": decision}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
