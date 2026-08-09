#!/usr/bin/env python3
"""Run a transparent local repair-loop proof.

The default is deliberately a fixture simulation. It proves the sequencing and
audit record without pretending that a local run mutated DataHub. A real
write-back run belongs in scripts/writeback_datahub.py with an authorized
deployment token and --transport rest.
"""

from __future__ import annotations

import argparse
import json

from metagate.repair_proof import run_fixture_repair_proof


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = run_fixture_repair_proof()
    print(json.dumps(result, indent=2) if args.json else json.dumps({
        "status": result["status"],
        "transport": result["repair"].get("transport"),
        "before": result["before"]["decision"],
        "after": result["after"]["decision"],
        "poll_attempts": result["indexing"]["attempts"],
        "score_delta": result["score_delta"],
        "audit_events": [event["event_type"] for event in result["audit_events"]],
        "proof_note": result["proof_note"],
    }, indent=2))


if __name__ == "__main__":
    main()
