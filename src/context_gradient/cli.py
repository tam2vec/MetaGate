from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

from context_gradient.datahub.adapter import DataHubEvidenceExtractor, DataHubWriteback, GraphQLDataHubClient
from context_gradient.datahub.mock_client import FileDataHubClient
from context_gradient.scanner import BackgroundScanner
from context_gradient.sdk.cache import JsonCache
from context_gradient.sdk.admission import admit_capability
from context_gradient.sdk.reports import explain_certificate
from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.history import ReadinessHistory
from context_gradient.sdk.policy import load_policy


def _predicate_expression(required_evidence: list) -> str:
    terms = []
    for item in required_evidence:
        if item.value == "incidents":
            terms.append("incidents.open == 0")
        else:
            terms.append(f"{item.value}.present")
    return " && ".join(terms) if terms else "true"


def _action_predicate(certificate: dict, policy, capability: str, allowed: bool) -> dict:
    capability_policy = next(
        (item for item in policy.capability_policies if item.name == capability),
        None,
    )
    expression = _predicate_expression(capability_policy.required_evidence if capability_policy else [])
    failed_terms = []
    for gap in certificate.get("gaps", []):
        if capability in gap.get("blocks", []):
            evidence_kind = gap.get("evidence_kind")
            failed_terms.append(
                "incidents.open == 0" if evidence_kind == "incidents" else f"{evidence_kind}.present"
            )
    matching = next(
        (item for item in certificate.get("certified_capabilities", []) if item["capability"] == capability),
        {},
    )
    for reason in matching.get("reasons", []):
        if reason.startswith("Readiness score below"):
            failed_terms.append("readiness_score >= policy.minimum_score")
        elif reason.startswith("Confidence below"):
            failed_terms.append("confidence >= policy.minimum_confidence")
    return {
        "action": capability,
        "predicate": expression,
        "result": bool(allowed),
        "failed_terms": list(dict.fromkeys(term for term in failed_terms if term)),
        "decision": "allowed" if allowed else "blocked",
    }


def _record_live_run(path: str | Path, certificate: dict, decision: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        runs = json.loads(target.read_text())
    else:
        runs = []
    runs.append(
        {
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "entity_urn": decision["entity_urn"],
            "asset": decision["entity_urn"].split(",")[-2] if "," in decision["entity_urn"] else decision["entity_urn"],
            "capability": decision["capability"],
            "allowed": decision["allowed"],
            "decision": "allowed" if decision["allowed"] else "blocked",
            "reason": decision["reason"],
            "readiness_score": certificate.get("readiness_score"),
            "confidence": certificate.get("confidence"),
            "policy": certificate.get("metadata", {}).get("policy"),
            "evidence": decision.get("evidence", []),
            "action_predicate": decision.get("action_predicate", {}),
        }
    )
    target.write_text(json.dumps(runs, indent=2, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="predicate",
        description="Decide when AI is allowed to act on DataHub entities.",
    )
    parser.add_argument("urn", help="DataHub entity URN")
    parser.add_argument("--policy", required=True, help="YAML policy profile")
    parser.add_argument("--datahub-file", help="Local DataHub fixture or exported graph JSON")
    parser.add_argument("--datahub-url", help="Live DataHub GraphQL endpoint; defaults to DATAHUB_GRAPHQL_URL")
    parser.add_argument("--cache-file", default=".context-gradient/cache.json")
    parser.add_argument("--history-dir", default=".context-gradient/history")
    parser.add_argument("--writeback-file", default=".context-gradient/writeback.json")
    parser.add_argument("--request-capability", help="Evaluate one agent action against the Predicate Certificate")
    parser.add_argument("--record-live-run", action="store_true", help="Append this capability decision to the live proof data file")
    parser.add_argument("--live-runs-file", default="examples/outputs/live-runs.json", help="Path used by --record-live-run")
    parser.add_argument("--explain", action="store_true", help="Print evidence-to-decision explanation")
    args = parser.parse_args()

    if args.datahub_url or not args.datahub_file:
        client = GraphQLDataHubClient(args.datahub_url)
    else:
        client = FileDataHubClient(args.datahub_file, args.writeback_file)
    policy = load_policy(args.policy)
    scanner = BackgroundScanner(
        extractor=DataHubEvidenceExtractor(client, cache=JsonCache(args.cache_file)),
        engine=ReadinessEngine(policy),
        history=ReadinessHistory(Path(args.history_dir)),
        writeback=DataHubWriteback(client),
    )
    result = scanner.handle_metadata_events([args.urn])[0]
    output = result.certificate
    if args.request_capability:
        decision = admit_capability(output, args.request_capability).__dict__
        decision["action_predicate"] = _action_predicate(
            output,
            policy,
            args.request_capability,
            decision["allowed"],
        )
        if args.record_live_run:
            _record_live_run(args.live_runs_file, output, decision)
        output = decision
    elif args.explain:
        output = explain_certificate(output)
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
