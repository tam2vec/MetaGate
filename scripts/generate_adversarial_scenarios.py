#!/usr/bin/env python3
"""Write the reproducible synthetic adversarial proof set."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from metagate.adversarial_scenarios import CATEGORIES, generate_scenarios


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count-per-category", type=int, default=5)
    parser.add_argument(
        "--output",
        default="examples/adversarial/scenarios.json",
    )
    parser.add_argument("--json", action="store_true", help="Print a machine-readable summary")
    args = parser.parse_args()
    scenarios = generate_scenarios(args.count_per_category)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "kind": "synthetic_adversarial_proof",
                "independent_human_labels": False,
                "categories": list(CATEGORIES),
                "count": len(scenarios),
                "scenarios": scenarios,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if args.json:
        print(json.dumps({
            "status": "generated",
            "count": len(scenarios),
            "output": str(output),
            "label_source": "synthetic_rule",
            "independent_human_labels": False,
        }))
    else:
        print(f"Wrote {len(scenarios)} synthetic adversarial scenarios to {output}")


if __name__ == "__main__":
    main()
