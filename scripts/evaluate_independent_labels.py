from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from context_gradient.datahub.adapter import DataHubEvidenceExtractor, DEFAULT_MAX_HOPS
from context_gradient.datahub.mock_client import FileDataHubClient
from context_gradient.sdk.admission import enforce_action_guardrails
from context_gradient.sdk.cache import JsonCache
from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.policy import load_policy


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"yes", "y", "true", "1", "agree", "correct"}


def _expected_gate(label: str) -> str:
    """Borderline is a safety stop, not an allow decision."""
    normalized = label.strip().lower()
    if normalized == "borderline":
        return "blocked"
    return normalized


def main() -> None:
    parser = argparse.ArgumentParser(description="Score independently labeled MetaGate decisions.")
    parser.add_argument("--labels", default="examples/benchmark/independent-label-template.csv")
    parser.add_argument("--output", default="examples/outputs/independent-label-report.json")
    parser.add_argument(
        "--datahub-file",
        help="Recompute MetaGate decisions from a graph fixture before comparing them to labels.",
    )
    parser.add_argument("--policy", help="Policy used with --datahub-file")
    parser.add_argument("--max-hops", type=int, default=DEFAULT_MAX_HOPS)
    parser.add_argument(
        "--minimum-labels",
        type=int,
        default=30,
        help="Minimum completed human-labeled cases reported as the target (default: 30).",
    )
    parser.add_argument(
        "--require-minimum",
        action="store_true",
        help="Fail unless the label file contains at least --minimum-labels completed cases.",
    )
    args = parser.parse_args()

    label_path = Path(args.labels)
    rows = list(csv.DictReader(label_path.read_text().splitlines()))
    if args.datahub_file and not args.policy:
        raise SystemExit("--policy is required when --datahub-file is supplied.")

    if args.datahub_file:
        client = FileDataHubClient(args.datahub_file)
        engine = ReadinessEngine(load_policy(args.policy))
        extractor = DataHubEvidenceExtractor(client, max_hops=args.max_hops)
        for row in rows:
            if row.get("human_label") and row.get("asset_urn") and row.get("capability"):
                try:
                    certificate = engine.certify(extractor.bundle(row["asset_urn"])).as_dict()
                except (KeyError, RuntimeError) as error:
                    row["evaluation_error"] = str(error)
                    continue
                decision = enforce_action_guardrails(certificate, row["capability"])
                row["metagate_decision"] = "allowed" if decision.allowed else "blocked"
                row["metagate_readiness"] = certificate["readiness_score"]
                row["metagate_confidence"] = certificate["confidence"]
                row["human_decision"] = row["human_label"]
                row["human_agrees"] = "yes"

    # Support both the original completed-label format and the more useful
    # human_label format used for fresh reviews.
    valid_labels = {"allowed", "blocked", "borderline"}
    invalid_labels = [
        row for row in rows
        if row.get("human_label") and row["human_label"].strip().lower() not in valid_labels
    ]
    if invalid_labels:
        raise SystemExit(
            "Invalid human_label value. Use allowed, blocked, or borderline."
        )

    # A human's borderline judgment is deliberately evaluated as a block:
    # uncertainty must not become permission for autonomous action.
    for row in rows:
        if row.get("human_decision"):
            row["human_decision"] = _expected_gate(row["human_decision"])

    completed = [
        row for row in rows
        if row.get("metagate_decision") and row.get("human_decision")
    ]
    if not completed:
        raise SystemExit(
            "No completed labels found. Fill metagate_decision/human_decision "
            "or provide --datahub-file and --policy."
        )

    label_shortfall = max(0, args.minimum_labels - len(completed))
    if args.require_minimum and label_shortfall:
        raise SystemExit(
            f"Only {len(completed)} completed human labels found; "
            f"at least {args.minimum_labels} are required."
        )

    matches = [
        row for row in completed
        if row["metagate_decision"].strip().lower() == _expected_gate(row["human_decision"])
        and (not row.get("human_agrees") or _truthy(row["human_agrees"]))
    ]
    disagreements = [
        row for row in completed
        if row["metagate_decision"].strip().lower() != _expected_gate(row["human_decision"])
        or (row.get("human_agrees") and not _truthy(row["human_agrees"]))
    ]
    report = {
        "label_file": str(label_path),
        "completed_labels": len(completed),
        "minimum_labels": args.minimum_labels,
        "label_shortfall": label_shortfall,
        "minimum_satisfied": label_shortfall == 0,
        "accepted_human_labels": sorted(valid_labels),
        "matches": len(matches),
        "disagreements": len(disagreements),
        "agreement_rate": round(len(matches) / len(completed), 4),
        "claim_boundary": (
            "Independent label agreement only applies to the supplied reviewer-labeled cases. "
            "It is not a production accuracy claim."
        ),
        "disagreement_urns": [row.get("asset_urn") for row in disagreements],
        "decision_rows": [
            {
                "asset_urn": row.get("asset_urn"),
                "capability": row.get("capability"),
                "metagate_decision": row.get("metagate_decision"),
                "human_decision": row.get("human_decision"),
                "human_label": row.get("human_label"),
                "labeler_role": row.get("labeler_role"),
                "readiness": row.get("metagate_readiness"),
                "confidence": row.get("metagate_confidence"),
            }
            for row in completed
        ],
        "unevaluated_rows": [
            {"asset_urn": row.get("asset_urn"), "error": row.get("evaluation_error")}
            for row in rows if row.get("evaluation_error")
        ],
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
