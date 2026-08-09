#!/usr/bin/env python3
"""Run a real, explicitly authorized MetaGate repair loop.

The loop is deliberately conservative:

* evaluation is read-only;
* no repair command is invented or run by default;
* a repair command must be supplied by the operator and confirmed with ``--yes``;
* DataHub is polled after the repair before the asset is evaluated again;
* optional MetaGate contract write-back still requires the existing verified
  write-back adapter and ``--yes``.

The command is useful for a local DataHub demo and is not a universal DataHub
mutation abstraction. The supplied repair command must target the deployment's
own supported mutation or ingestion workflow.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

from context_gradient.cli import _action_metagate
from context_gradient.datahub.adapter import (
    DataHubEvidenceExtractor,
    DataHubRestWritebackClient,
    DataHubWriteback,
    GraphQLDataHubClient,
)
from context_gradient.sdk.admission import enforce_action_guardrails
from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.policy import load_policy
from metagate.repair_loop import run_repair_loop


def _evaluate(extractor: DataHubEvidenceExtractor, engine: ReadinessEngine, policy: Any, urn: str, capability: str) -> dict[str, Any]:
    certificate = engine.certify(extractor.bundle(urn)).as_dict()
    decision = enforce_action_guardrails(certificate, capability)
    action_metagate = _action_metagate(certificate, policy, capability, decision.allowed)
    result = dict(certificate)
    result.update(
        {
            "decision": "allowed" if decision.allowed else "blocked",
            "allowed": decision.allowed,
            "capability": capability,
            "reason": decision.reason,
            "failed": [item.get("evidence_kind") for item in certificate.get("gaps", [])],
            "action_metagate": action_metagate,
            "metagate_decision": action_metagate,
        }
    )
    return result


def _repair_command(command: str, before: dict[str, Any]) -> dict[str, Any]:
    """Run the operator-supplied repair and require an explicit JSON receipt."""
    completed = subprocess.run(
        shlex.split(command),
        input=json.dumps({"entity_urn": before.get("entity_urn"), "before": before}),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return {
            "status": "error",
            "applied": False,
            "returncode": completed.returncode,
            "stderr": completed.stderr.strip()[-2000:],
        }
    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as error:
        return {
            "status": "error",
            "applied": False,
            "returncode": completed.returncode,
            "error": f"repair command must print a JSON receipt: {error}",
            "stdout": completed.stdout.strip()[-2000:],
        }
    if not isinstance(payload, dict) or payload.get("applied") is not True:
        return {
            "status": "error",
            "applied": False,
            "returncode": completed.returncode,
            "error": "repair receipt must contain applied: true",
            "receipt": payload,
        }
    return {"status": "applied", "returncode": 0, **payload}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a live MetaGate repair, poll, and re-evaluation loop")
    parser.add_argument("urn")
    parser.add_argument("--policy", required=True)
    parser.add_argument("--datahub-url", default=os.environ.get("DATAHUB_GRAPHQL_URL"), required=not os.environ.get("DATAHUB_GRAPHQL_URL"))
    parser.add_argument("--datahub-gms-url", default=os.environ.get("DATAHUB_GMS_URL"))
    parser.add_argument("--capability", default="autonomous-agent-action")
    parser.add_argument("--repair-command", help="Deployment-specific command that reads JSON on stdin and prints {\"applied\": true, ...}")
    parser.add_argument("--max-attempts", type=int, default=8)
    parser.add_argument("--poll-interval", type=float, default=0.5)
    parser.add_argument("--write-contract", action="store_true", help="Write the final MetaGate contract through the verified adapter")
    parser.add_argument("--transport", choices=("rest", "graphql"), default="rest")
    parser.add_argument("--mutation-file", help="Deployment-approved GraphQL mutation document")
    parser.add_argument("--verify-query-file", help="GraphQL query that returns the written contract")
    parser.add_argument("--yes", action="store_true", help="Confirm the repair/write targets a non-production namespace")
    args = parser.parse_args()

    if not args.repair_command and not args.write_contract:
        parser.error("Supply --repair-command for a real repair, or use the fixture runner for a sequencing-only demo.")
    if not args.yes:
        parser.error("Add --yes only after confirming this targets a non-production namespace.")
    if args.write_contract and args.transport == "graphql" and (not args.mutation_file or not args.verify_query_file):
        parser.error("--transport graphql requires --mutation-file and --verify-query-file")

    policy = load_policy(args.policy)
    client = GraphQLDataHubClient(args.datahub_url, token=os.environ.get("DATAHUB_TOKEN"))
    extractor = DataHubEvidenceExtractor(client)
    engine = ReadinessEngine(policy)
    before = _evaluate(extractor, engine, policy, args.urn, args.capability)

    def repair() -> dict[str, Any]:
        if not args.repair_command:
            return {"status": "not_configured", "applied": False, "error": "No repair command supplied."}
        return _repair_command(args.repair_command, before)

    def poll(attempt: int) -> dict[str, Any]:
        # A successful read proves the graph is readable after the mutation;
        # the after-evaluation is what proves whether the requested evidence
        # actually changed.
        bundle = extractor.bundle(args.urn)
        observed_at = bundle.entity.properties.get("_datahub_observation", {}).get("observed_at")
        return {
            "status": "ready",
            "readable": True,
            "attempt": attempt,
            "source_observed_at": observed_at,
        }

    def evaluate() -> dict[str, Any]:
        extractor.invalidate(args.urn)
        return _evaluate(extractor, engine, policy, args.urn, args.capability)

    result = run_repair_loop(
        before,
        repair=repair,
        poll=poll,
        evaluate=evaluate,
        max_attempts=max(1, args.max_attempts),
        poll_interval=max(0.0, args.poll_interval),
    )

    if args.write_contract and result.get("after"):
        after = result["after"]
        if args.transport == "rest":
            gms_url = args.datahub_gms_url or args.datahub_url.removesuffix("/api/graphql")
            writer = DataHubWriteback(DataHubRestWritebackClient(gms_url, token=os.environ.get("DATAHUB_TOKEN")))
        else:
            os.environ["DATAHUB_CERTIFICATE_MUTATION"] = Path(args.mutation_file).read_text()
            os.environ["DATAHUB_CERTIFICATE_QUERY"] = Path(args.verify_query_file).read_text()
            writer = DataHubWriteback(client)
        result["writeback"] = writer.publish(args.urn, after)

    print(json.dumps({"product": "MetaGate", "repair_loop": result}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
