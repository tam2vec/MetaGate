"""Evaluate one asset and write/read back its Predicate contract in DataHub."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from context_gradient.cli import _action_predicate
from context_gradient.datahub.adapter import (
    DataHubEvidenceExtractor,
    DataHubRestWritebackClient,
    DataHubWriteback,
    GraphQLDataHubClient,
)
from context_gradient.sdk.admission import enforce_action_guardrails
from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.policy import load_policy


def main() -> None:
    parser = argparse.ArgumentParser(description="Predicate DataHub write-back with read-after-write verification.")
    parser.add_argument("urn")
    parser.add_argument("--policy", required=True)
    parser.add_argument("--datahub-url", default=os.environ.get("DATAHUB_GRAPHQL_URL"), required=not os.environ.get("DATAHUB_GRAPHQL_URL"))
    parser.add_argument(
        "--datahub-gms-url",
        default=os.environ.get("DATAHUB_GMS_URL"),
        help="DataHub GMS base URL for REST write-back, e.g. http://localhost:8080",
    )
    parser.add_argument("--capability", default="autonomous-agent-action")
    parser.add_argument("--transport", choices=("rest", "graphql"), default="rest")
    parser.add_argument("--mutation-file", help="Deployment-approved GraphQL mutation document")
    parser.add_argument("--verify-query-file", help="GraphQL query that returns the written contract")
    parser.add_argument("--yes", action="store_true", help="Confirm this is a non-production write-back test")
    args = parser.parse_args()
    if not args.yes:
        parser.error("Add --yes only after confirming this targets a non-production namespace.")

    if args.transport == "graphql" and (not args.mutation_file or not args.verify_query_file):
        parser.error("--transport graphql requires --mutation-file and --verify-query-file")
    client = GraphQLDataHubClient(args.datahub_url, token=os.environ.get("DATAHUB_TOKEN"))
    policy = load_policy(args.policy)
    certificate = ReadinessEngine(policy).certify(DataHubEvidenceExtractor(client).bundle(args.urn)).as_dict()
    decision = enforce_action_guardrails(certificate, args.capability).__dict__
    decision["action_predicate"] = _action_predicate(certificate, policy, args.capability, decision["allowed"])
    certificate["predicate_decision"] = decision["action_predicate"]
    if args.transport == "rest":
        gms_url = args.datahub_gms_url or args.datahub_url.removesuffix("/api/graphql")
        writeback_client = DataHubRestWritebackClient(gms_url, token=os.environ.get("DATAHUB_TOKEN"))
    else:
        os.environ["DATAHUB_CERTIFICATE_MUTATION"] = Path(args.mutation_file).read_text()
        os.environ["DATAHUB_CERTIFICATE_QUERY"] = Path(args.verify_query_file).read_text()
        writeback_client = client
    receipt = DataHubWriteback(writeback_client).publish(args.urn, certificate)
    print(json.dumps({"product": "Predicate", "writeback": receipt, "decision": decision}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
