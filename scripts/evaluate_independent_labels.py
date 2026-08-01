from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"yes", "y", "true", "1", "agree", "correct"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Score independently labeled Predicate decisions.")
    parser.add_argument("--labels", default="examples/benchmark/independent-label-template.csv")
    parser.add_argument("--output", default="examples/outputs/independent-label-report.json")
    args = parser.parse_args()

    label_path = Path(args.labels)
    rows = list(csv.DictReader(label_path.read_text().splitlines()))
    completed = [
        row for row in rows
        if row.get("predicate_decision") and row.get("human_decision") and row.get("human_agrees")
    ]
    if not completed:
        raise SystemExit(
            "No completed labels found. Fill predicate_decision, human_decision, "
            "human_agrees, and reviewer_notes first."
        )

    matches = [
        row for row in completed
        if row["predicate_decision"].strip().lower() == row["human_decision"].strip().lower()
        and _truthy(row["human_agrees"])
    ]
    disagreements = [
        row for row in completed
        if row["predicate_decision"].strip().lower() != row["human_decision"].strip().lower()
        or not _truthy(row["human_agrees"])
    ]
    report = {
        "label_file": str(label_path),
        "completed_labels": len(completed),
        "matches": len(matches),
        "disagreements": len(disagreements),
        "agreement_rate": round(len(matches) / len(completed), 4),
        "claim_boundary": (
            "Independent label agreement only applies to the supplied reviewer-labeled cases. "
            "It is not a production accuracy claim."
        ),
        "disagreement_urns": [row.get("asset_urn") for row in disagreements],
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
