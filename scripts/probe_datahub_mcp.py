"""Probe the separately installed official DataHub MCP server."""

from __future__ import annotations

import argparse
import json
import os

from predicate.datahub_mcp_probe import probe_datahub_mcp

DEFAULT_URN = "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)"


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the official DataHub MCP server can inspect one URN")
    parser.add_argument("--urn", default=DEFAULT_URN)
    parser.add_argument("--command", default=os.environ.get("PREDICATE_DATAHUB_MCP_COMMAND"))
    args = parser.parse_args()
    print(json.dumps(probe_datahub_mcp(args.urn, args.command), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
