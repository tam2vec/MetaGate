from __future__ import annotations

import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

from context_gradient.datahub.adapter import (
    DEFAULT_MAX_HOPS,
    DataHubEvidenceExtractor,
    DataHubWriteback,
    GraphQLDataHubClient,
)
from context_gradient.datahub.mock_client import FileDataHubClient
from context_gradient.scanner import BackgroundScanner
from context_gradient.sdk.cache import JsonCache
from context_gradient.sdk.admission import enforce_action_guardrails
from context_gradient.sdk.assessment import required_evidence_for_action
from context_gradient.sdk.reports import explain_certificate
from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.history import ReadinessHistory
from context_gradient.sdk.policy import load_policy
from metagate.contracts import build_constraint_contract
from metagate.agent_registry import apply_agent_registry_gate, resolve_agent_context


def _metagate_expression(required_evidence: list) -> str:
    terms = []
    for item in required_evidence:
        if item.value == "incidents":
            terms.append("incidents.open == 0")
        else:
            terms.append(f"{item.value}.present")
    return " && ".join(terms) if terms else "true"


def _action_metagate(
    certificate: dict,
    policy,
    capability: str,
    allowed: bool,
    guardrail_reason: str | None = None,
) -> dict:
    capability_policy = next(
        (item for item in policy.capability_policies if item.name == capability),
        None,
    )
    profile_required = certificate.get("metadata", {}).get("assessment", {}).get("required_evidence", [])
    required = required_evidence_for_action(
        capability_policy.required_evidence if capability_policy else [],
        profile_required,
        capability,
    )
    expression = _metagate_expression(required)
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
    if guardrail_reason and not allowed:
        failed_terms.append("action.guardrail")
    return {
        "action": capability,
        "metagate": expression,
        "result": bool(allowed),
        "failed_terms": list(dict.fromkeys(term for term in failed_terms if term)),
        "reasons": [guardrail_reason] if guardrail_reason and not allowed else [],
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
            "action_metagate": decision.get("action_metagate", {}),
        }
    )
    target.write_text(json.dumps(runs, indent=2, sort_keys=True) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="metagate",
        description="Decide when AI is allowed to act on DataHub entities.",
    )
    parser.add_argument("urn", help="DataHub entity URN")
    parser.add_argument("--policy", required=True, help="YAML policy profile")
    parser.add_argument("--datahub-file", help="Local DataHub fixture or exported graph JSON")
    parser.add_argument("--datahub-url", help="Live DataHub GraphQL endpoint; defaults to DATAHUB_GRAPHQL_URL")
    parser.add_argument("--cache-file", default=".context-gradient/cache.json")
    parser.add_argument(
        "--max-hops",
        type=int,
        default=DEFAULT_MAX_HOPS,
        help="Lineage graph scope. Review uses the same default (one direct hop).",
    )
    parser.add_argument("--history-dir", default=".context-gradient/history")
    parser.add_argument("--writeback-file", default=".context-gradient/writeback.json")
    parser.add_argument("--request-capability", help="Evaluate one agent action against the MetaGate Certificate")
    parser.add_argument("--registry-file", help="DataHub-shaped Agent Registry and Service Catalog JSON")
    parser.add_argument("--agent-id", help="Registered DataHub agent URN")
    parser.add_argument("--skill-id", help="Registered DataHub skill URN")
    parser.add_argument("--tool-id", help="Registered DataHub API/tool URN")
    parser.add_argument("--service-id", help="Registered DataHub service URN")
    parser.add_argument(
        "--require-agent-registry",
        action="store_true",
        help="Fail closed unless the agent, skill, tool, and service chain is verified.",
    )
    parser.add_argument(
        "--enable-writeback",
        action="store_true",
        help="Explicitly publish through configured DataHub mutation documents.",
    )
    parser.add_argument("--record-live-run", action="store_true", help="Append this capability decision to the live proof data file")
    parser.add_argument("--live-runs-file", default="examples/outputs/live-runs.json", help="Path used by --record-live-run")
    parser.add_argument("--explain", action="store_true", help="Print evidence-to-decision explanation")
    args = parser.parse_args()

    if args.datahub_url or not args.datahub_file:
        client = GraphQLDataHubClient(args.datahub_url)
    else:
        client = FileDataHubClient(args.datahub_file, args.writeback_file)
    policy = load_policy(args.policy)
    writeback = DataHubWriteback(client) if args.enable_writeback else None
    # Live DataHub runs must read current metadata; fixture/file runs may use
    # the cache for fast repeated evaluations.
    cache = None if isinstance(client, GraphQLDataHubClient) else JsonCache(args.cache_file)
    scanner = BackgroundScanner(
        extractor=DataHubEvidenceExtractor(client, cache=cache, max_hops=args.max_hops),
        engine=ReadinessEngine(policy),
        history=ReadinessHistory(Path(args.history_dir)),
        writeback=writeback,
    )
    result = scanner.handle_metadata_events([args.urn])[0]
    output = result.certificate
    if args.request_capability:
        decision = enforce_action_guardrails(output, args.request_capability).__dict__
        decision["decision"] = "allowed" if decision["allowed"] else "blocked"
        decision["action_metagate"] = _action_metagate(
            output,
            policy,
            args.request_capability,
            decision["allowed"],
            decision.get("reason"),
        )
        now = datetime.now(timezone.utc).isoformat()
        decision["decision_id"] = f"pred-{int(datetime.now(timezone.utc).timestamp() * 1000)}"
        decision["evaluated_at"] = now
        assessment = output.get("metadata", {}).get("assessment", {})
        decision["facts"] = assessment.get("facts", {})
        decision["guidance"] = assessment.get("guidance", [])
        decision["score_trace"] = output.get("metadata", {}).get("score_trace", {})
        decision["datahub_observation"] = output.get("metadata", {}).get("datahub_observation", {})
        decision["gaps"] = output.get("gaps", [])
        agent_context = resolve_agent_context(
            registry_path=args.registry_file,
            dataset_urn=args.urn,
            agent_id=args.agent_id,
            skill_id=args.skill_id,
            tool_id=args.tool_id,
            service_id=args.service_id,
            requested=args.require_agent_registry,
            capability=args.request_capability,
        )
        decision["registry_required"] = bool(args.require_agent_registry)
        decision["agent_context"] = agent_context
        decision["registry_evidence"] = agent_context
        if args.require_agent_registry:
            apply_agent_registry_gate(decision, agent_context, args.request_capability)
            decision["failed_terms"] = decision.get("action_metagate", {}).get("failed_terms", [])
        decision["constraint_contract"] = build_constraint_contract(decision, args.request_capability)
        if args.record_live_run:
            _record_live_run(args.live_runs_file, output, decision)
        output = decision
    elif args.explain:
        output = explain_certificate(output)
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
