#!/usr/bin/env python3
"""Run the MetaGate DataHub Action adapter from an event payload."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from metagate.datahub_action import handle_action  # noqa: E402
from metagate.review import ReviewState  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MetaGate as a DataHub Action adapter.")
    parser.add_argument("--payload", help="JSON event payload; stdin is used when omitted.")
    parser.add_argument("--policy", default="examples/policies/enterprise_ai.yml")
    parser.add_argument("--datahub-url", default=os.environ.get("DATAHUB_GRAPHQL_URL"))
    parser.add_argument("--datahub-file")
    args = parser.parse_args()
    raw = args.payload if args.payload is not None else sys.stdin.read()
    payload = json.loads(raw or "{}")
    state = ReviewState(args.policy, args.datahub_url, args.datahub_file, allow_recorded_fallback=False)
    print(json.dumps(handle_action(payload, lambda urn, capability: state.evaluate(urn, capability, refresh=True)), indent=2))


if __name__ == "__main__":
    main()

