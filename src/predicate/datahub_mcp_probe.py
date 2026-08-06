"""Optional probe for DataHub's official MCP server."""

from __future__ import annotations

import json
import os
import selectors
import shlex
import subprocess
import time
from itertools import count
from typing import Any

from predicate.mcp_evidence import normalize_mcp_entity_output, normalize_mcp_query_output

DEFAULT_TIMEOUT_SECONDS = 8.0
REQUIRED_TOOLS = ("search", "get_entities", "get_lineage", "list_schema_fields")
OPTIONAL_TOOLS = ("get_dataset_queries",)


class MCPProbeError(RuntimeError):
    """A safe, user-facing MCP probe failure."""


class DataHubMCPProbe:
    def __init__(self, command: str | None = None, *, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self.command = command if command is not None else os.environ.get("PREDICATE_DATAHUB_MCP_COMMAND", "")
        self.timeout_seconds = max(1.0, float(timeout_seconds))
        self._request_ids = count(1)

    def run(self, urn: str) -> dict[str, Any]:
        if not self.command.strip():
            return {
                "status": "not_configured",
                "server": "DataHub official MCP server",
                "checked_urn": urn,
                "required_tools": list(REQUIRED_TOOLS),
                "note": "Set PREDICATE_DATAHUB_MCP_COMMAND to the approved official DataHub MCP startup command to run this proof.",
            }
        if not urn.strip():
            return {"status": "attention_required", "error": "urn is required"}
        process: subprocess.Popen[bytes] | None = None
        try:
            command = shlex.split(self.command)
            if not command:
                raise MCPProbeError("PREDICATE_DATAHUB_MCP_COMMAND is empty")
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
                env=os.environ.copy(),
            )
            initialize = self._request(process, "initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "predicate", "version": "0.1.0"},
            })
            self._notification(process, "notifications/initialized", {})
            listed = self._request(process, "tools/list", {})
            tools = listed.get("tools", []) if isinstance(listed, dict) else []
            tool_map = {
                item.get("name"): item for item in tools
                if isinstance(item, dict) and isinstance(item.get("name"), str)
            }
            missing_tools = [name for name in REQUIRED_TOOLS if name not in tool_map]
            result: dict[str, Any] = {
                "status": "attention_required" if missing_tools else "verified",
                "server": "DataHub official MCP server",
                "checked_urn": urn,
                "server_info": initialize.get("serverInfo", {}) if isinstance(initialize, dict) else {},
                "tool_names": sorted(tool_map),
                "required_tools": list(REQUIRED_TOOLS),
                "optional_tools": list(OPTIONAL_TOOLS),
                "missing_required_tools": missing_tools,
            }
            entity_tool = tool_map.get("get_entities")
            arguments = self._entity_arguments(entity_tool, urn) if entity_tool else None
            if arguments is None:
                result["status"] = "attention_required"
                result["entity_call"] = {"status": "not_run", "reason": "get_entities input schema did not expose urn or urns"}
            else:
                entity = self._request(process, "tools/call", {"name": "get_entities", "arguments": arguments})
                normalized = normalize_mcp_entity_output(entity, urn)
                result["entity_call"] = {
                    "status": "ok" if normalized.get("entity_found") else "attention_required",
                    "argument_shape": sorted(arguments),
                    "returned_content": bool(entity.get("content")) if isinstance(entity, dict) else bool(entity),
                    "content_blocks": normalized.get("content_blocks", 0),
                    "entity_found": normalized.get("entity_found", False),
                    "returned_fields": normalized.get("returned_fields", []),
                    "evidence": normalized.get("evidence", {}),
                    "facts": normalized.get("facts", {}),
                    "notes": normalized.get("notes", []),
                }
            query_tool = tool_map.get("get_dataset_queries")
            query_arguments = self._query_arguments(query_tool, urn) if query_tool else None
            if query_arguments is not None:
                query_result = self._request(
                    process,
                    "tools/call",
                    {"name": "get_dataset_queries", "arguments": query_arguments},
                )
                normalized_queries = normalize_mcp_query_output(query_result)
                result["query_call"] = {
                    "status": normalized_queries["status"],
                    "argument_shape": sorted(query_arguments),
                    "query_count": normalized_queries["query_count"],
                    "latest_query_at": normalized_queries["latest_query_at"],
                    "content_blocks": normalized_queries["content_blocks"],
                    "notes": normalized_queries["notes"],
                }
            else:
                result["query_call"] = {
                    "status": "not_available",
                    "reason": "get_dataset_queries is optional or its input schema did not expose a dataset identifier",
                }
            if result["status"] == "verified" and result["entity_call"]["status"] != "ok":
                result["status"] = "attention_required"
            return result
        except Exception as error:
            return {
                "status": "attention_required",
                "server": "DataHub official MCP server",
                "checked_urn": urn,
                "error": self._safe_error(error),
                "note": "Confirm the official MCP command, DataHub URL, token, and transport configuration.",
            }
        finally:
            if process is not None:
                self._stop(process)

    def _request(self, process: subprocess.Popen[bytes], method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = next(self._request_ids)
        self._write_frame(process, {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            message = self._read_frame(process, deadline)
            if message is None or message.get("id") != request_id:
                continue
            if "error" in message:
                error = message["error"]
                raise MCPProbeError(str(error.get("message", error)))
            value = message.get("result", {})
            return value if isinstance(value, dict) else {"value": value}
        raise MCPProbeError(f"timed out waiting for MCP response to {method}")

    def _notification(self, process: subprocess.Popen[bytes], method: str, params: dict[str, Any]) -> None:
        self._write_frame(process, {"jsonrpc": "2.0", "method": method, "params": params})

    @staticmethod
    def _write_frame(process: subprocess.Popen[bytes], payload: dict[str, Any]) -> None:
        if process.stdin is None:
            raise MCPProbeError("MCP process stdin is unavailable")
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        process.stdin.write(b"Content-Length: " + str(len(encoded)).encode("ascii") + b"\r\n\r\n" + encoded)
        process.stdin.flush()

    def _read_frame(self, process: subprocess.Popen[bytes], deadline: float) -> dict[str, Any] | None:
        if process.stdout is None:
            raise MCPProbeError("MCP process stdout is unavailable")
        headers: dict[str, str] = {}
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise MCPProbeError("timed out waiting for MCP response")
                if not selector.select(remaining):
                    raise MCPProbeError("timed out waiting for MCP response")
                line = process.stdout.readline()
                if not line:
                    detail = self._stderr_detail(process)
                    raise MCPProbeError(f"MCP process closed its stdout{detail}")
                if line in {b"\r\n", b"\n"}:
                    break
                key, _, value = line.decode("ascii", "replace").partition(":")
                headers[key.lower()] = value.strip()
        finally:
            selector.close()
        length = int(headers.get("content-length", "0"))
        if not length:
            raise MCPProbeError("MCP response did not include Content-Length")
        payload = bytearray()
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        try:
            while len(payload) < length:
                remaining = deadline - time.monotonic()
                if remaining <= 0 or not selector.select(remaining):
                    raise MCPProbeError("timed out reading MCP response body")
                chunk = process.stdout.read(length - len(payload))
                if not chunk:
                    raise MCPProbeError("MCP response ended before its declared Content-Length")
                payload.extend(chunk)
        finally:
            selector.close()
        value = json.loads(bytes(payload).decode("utf-8"))
        return value if isinstance(value, dict) else None

    @staticmethod
    def _stderr_detail(process: subprocess.Popen[bytes]) -> str:
        if process.stderr is None:
            return ""
        try:
            data = process.stderr.read(2048).decode("utf-8", "replace").strip()
        except Exception:
            data = ""
        return f": {data}" if data else ""

    @staticmethod
    def _entity_arguments(tool: dict[str, Any] | None, urn: str) -> dict[str, Any] | None:
        schema = (tool or {}).get("inputSchema") or {}
        properties = schema.get("properties") if isinstance(schema, dict) else {}
        if isinstance(properties, dict) and "urns" in properties:
            return {"urns": [urn]}
        if isinstance(properties, dict) and "urn" in properties:
            return {"urn": urn}
        return None

    @staticmethod
    def _query_arguments(tool: dict[str, Any] | None, urn: str) -> dict[str, Any] | None:
        schema = (tool or {}).get("inputSchema") or {}
        properties = schema.get("properties") if isinstance(schema, dict) else {}
        if not isinstance(properties, dict):
            return None
        for key in ("urn", "dataset_urn", "entity_urn"):
            if key in properties:
                return {key: urn}
        for key in ("urns", "dataset_urns", "entity_urns"):
            if key in properties:
                return {key: [urn]}
        return None

    @staticmethod
    def _safe_error(error: Exception) -> str:
        message = str(error).strip().replace("DATAHUB_TOKEN", "[redacted]")
        return message[:500] or error.__class__.__name__

    @staticmethod
    def _stop(process: subprocess.Popen[bytes]) -> None:
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=1)


def probe_datahub_mcp(urn: str, command: str | None = None) -> dict[str, Any]:
    return DataHubMCPProbe(command).run(urn)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Verify the official DataHub MCP server can inspect one URN")
    parser.add_argument(
        "--urn",
        default="urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)",
    )
    parser.add_argument("--command", default=os.environ.get("PREDICATE_DATAHUB_MCP_COMMAND"))
    args = parser.parse_args()
    print(json.dumps(probe_datahub_mcp(args.urn, args.command), indent=2, sort_keys=True))
