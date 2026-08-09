#!/usr/bin/env python3
"""Portable DataHub Action/webhook bridge for MetaGate.

Reads one JSON event from stdin, forwards it to MetaGate's guarded action
endpoint, and returns a fail-closed JSON response. No raw rows are forwarded.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_ENDPOINT = "http://127.0.0.1:8765/api/datahub-action"


def forward_event(payload: dict[str, Any], endpoint: str | None = None) -> dict[str, Any]:
    """Forward one DataHub event and return a safe decision-shaped response."""
    target = (endpoint or os.environ.get("METAGATE_ACTION_ENDPOINT") or DEFAULT_ENDPOINT).strip()
    if not target:
        return {
            "status": "not_configured",
            "decision": "blocked",
            "allowed": False,
            "reason": "METAGATE_ACTION_ENDPOINT is not configured.",
            "writeback": "read_only",
        }
    event = dict(payload)
    event.pop("rawRows", None)
    event.pop("rows", None)
    request = Request(
        target,
        data=json.dumps(event, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=float(os.environ.get("METAGATE_ACTION_TIMEOUT", "10"))) as response:
            result = json.loads(response.read().decode("utf-8"))
        return result if isinstance(result, dict) else {"status": "attention_required", "decision": "blocked", "allowed": False}
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as error:
        return {
            "status": "attention_required",
            "decision": "blocked",
            "allowed": False,
            "reason": f"MetaGate action endpoint could not be verified: {error}",
            "writeback": "read_only",
        }


def main() -> None:
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict):
        raise SystemExit("DataHub Action event must be a JSON object")
    print(json.dumps(forward_event(payload), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
