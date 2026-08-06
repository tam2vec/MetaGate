"""Diagnose the local Predicate and DataHub integration."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]


def check_url(url: str, method: str = "POST") -> tuple[bool, str]:
    try:
        request = Request(
            url,
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method=method,
        )
        with urlopen(request, timeout=5) as response:
            return True, f"HTTP {response.status}"
    except HTTPError as error:
        # GraphQL commonly rejects an empty probe with 400/500 while still
        # proving that the endpoint is reachable. Authentication and schema
        # checks belong to the actual evaluation command.
        return True, f"reachable (HTTP {error.code})"
    except Exception as error:
        return False, str(error)


def optional_mcp_status() -> tuple[bool, str]:
    """Report the optional official DataHub MCP configuration honestly.

    The official MCP server is a separate process and cannot be proven by
    checking that Predicate's own MCP server file exists. It is therefore an
    informational check: absent configuration is not a local setup failure.
    """
    command = os.environ.get("PREDICATE_DATAHUB_MCP_COMMAND", "").strip()
    if command:
        return True, f"configured; run predicate-datahub-mcp-probe to verify ({command})"
    return True, "optional / not configured; set PREDICATE_DATAHUB_MCP_COMMAND to verify it"


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Predicate and DataHub setup")
    parser.add_argument(
        "--datahub-url",
        default=os.environ.get("DATAHUB_GRAPHQL_URL", "http://localhost:8080/api/graphql"),
    )
    parser.add_argument("--predicate-url", default="http://127.0.0.1:8765")
    args = parser.parse_args()

    checks = []
    for name, url, method in (
        ("DataHub GraphQL", args.datahub_url, "POST"),
        ("Predicate Review API", f"{args.predicate_url}/healthz", "GET"),
    ):
        ok, detail = check_url(url, method)
        checks.append({"name": name, "required": True, "ok": ok, "detail": detail})
    checks.extend(
        [
            {
                "name": "extension source",
                "required": True,
                "ok": (ROOT / "examples/browser-extension/manifest.json").exists(),
                "detail": str(ROOT / "examples/browser-extension"),
            },
            {
                "name": "MCP server",
                "required": True,
                "ok": (ROOT / "src/predicate/mcp_server.py").exists(),
                "detail": "Predicate MCP (local read-only gate)",
            },
            {
                "name": "official DataHub MCP",
                "required": False,
                "ok": optional_mcp_status()[0],
                "detail": optional_mcp_status()[1],
            },
        ]
    )
    for item in checks:
        item["status"] = "verified" if item["ok"] else "unavailable"
        if not item["required"]:
            item["status"] = "informational" if item["ok"] else "optional_unavailable"
    required_checks = [item for item in checks if item["required"]]
    required_ready = all(item["ok"] for item in required_checks)
    payload = {
        "product": "Predicate",
        "checks": checks,
        "required_ready": required_ready,
        "ready": required_ready,
        "summary": (
            "Required local checks passed; optional official DataHub MCP is informational."
            if required_ready
            else "One or more required local checks are unavailable."
        ),
    }
    print(json.dumps(payload, indent=2))
    if not required_ready:
        print("\nFix the unavailable required checks, then rerun this command.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
