"""Small dependency-free MCP server for Predicate.

The server uses MCP's JSON-RPC stdio transport so an agent can call Predicate
without shelling out to the CLI. DataHub credentials remain in this process;
they are never returned as tool output.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from typing import Any

from context_gradient.datahub.adapter import DataHubEvidenceExtractor, GraphQLDataHubClient
from context_gradient.datahub.mock_client import FileDataHubClient
from context_gradient.cli import _action_predicate
from context_gradient.sdk.admission import enforce_action_guardrails
from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.policy import load_policy
from predicate.contracts import build_constraint_contract


def _result(payload: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, sort_keys=True)}]}


class PredicateMCP:
    def __init__(self, policy_path: str, datahub_url: str | None, token: str | None, datahub_file: str | None = None):
        if datahub_file and datahub_url:
            raise ValueError("Use either datahub_file or datahub_url, not both")
        self.policy = load_policy(policy_path)
        self.client = FileDataHubClient(datahub_file) if datahub_file else GraphQLDataHubClient(datahub_url, token=token)
        self.engine = ReadinessEngine(self.policy)

    def evaluate(self, arguments: dict[str, Any]) -> dict[str, Any]:
        urn = str(arguments.get("urn", "")).strip()
        capability = str(arguments.get("capability", "autonomous-agent-action")).strip()
        if not urn:
            raise ValueError("urn is required")
        bundle = DataHubEvidenceExtractor(self.client).bundle(urn)
        certificate = self.engine.certify(bundle).as_dict()
        admission = enforce_action_guardrails(certificate, capability)
        decision = admission.__dict__
        action_predicate = _action_predicate(
            certificate,
            self.policy,
            capability,
            admission.allowed,
            admission.reason,
        )
        verified_claims = certificate.get("context_contract", {}).get("verified_claims", [])
        result = {
            "entity_urn": urn,
            "capability": capability,
            "allowed": decision["allowed"],
            "decision": "allowed" if decision["allowed"] else "blocked",
            "readiness_score": certificate.get("readiness_score"),
            "confidence": certificate.get("confidence"),
            "reason": decision.get("reason"),
            "failed_terms": action_predicate["failed_terms"],
            "evidence": verified_claims,
            "action_predicate": action_predicate,
            "gaps": certificate.get("gaps", []),
            "datahub_observation": certificate.get("metadata", {}).get("datahub_observation", {}),
        }
        result["decision_id"] = f"pred-{int(datetime.now(timezone.utc).timestamp() * 1000)}"
        result["evaluated_at"] = datetime.now(timezone.utc).isoformat()
        result["score_trace"] = certificate.get("metadata", {}).get("score_trace", {})
        result["facts"] = certificate.get("metadata", {}).get("assessment", {}).get("facts", {})
        result["guidance"] = certificate.get("metadata", {}).get("assessment", {}).get("guidance", [])
        result["constraint_contract"] = build_constraint_contract(result, capability)
        return result

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "predicate_evaluate":
            return self.evaluate(arguments)
        if name == "predicate_evidence":
            result = self.evaluate(arguments)
            return {
                "entity_urn": result["entity_urn"],
                "readiness_score": result["readiness_score"],
                "confidence": result["confidence"],
                "evidence": result["evidence"],
                "gaps": result["gaps"],
                "observation": result["datahub_observation"],
            }
        if name == "predicate_constraint_contract":
            return self.evaluate(arguments)["constraint_contract"]
        raise ValueError(f"unknown tool: {name}")


TOOLS = [
    {
        "name": "predicate_evaluate",
        "description": "Evaluate whether a requested AI action is allowed for a DataHub asset.",
        "inputSchema": {
            "type": "object",
            "required": ["urn"],
            "properties": {
                "urn": {"type": "string", "description": "DataHub entity URN"},
                "capability": {"type": "string", "default": "autonomous-agent-action"},
            },
        },
    },
    {
        "name": "predicate_constraint_contract",
        "description": "Return the agent boundary: allowed and forbidden actions, human approval, permitted scope, and exact evidence.",
        "inputSchema": {
            "type": "object",
            "required": ["urn"],
            "properties": {"urn": {"type": "string"}, "capability": {"type": "string"}},
        },
    },
    {
        "name": "predicate_evidence",
        "description": "Return the evidence and gaps behind a Predicate decision.",
        "inputSchema": {
            "type": "object",
            "required": ["urn"],
            "properties": {"urn": {"type": "string"}, "capability": {"type": "string"}},
        },
    },
]


def _send(message: dict[str, Any]) -> None:
    encoded = json.dumps(message, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(encoded)}\r\n\r\n".encode("ascii"))
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


def _read() -> dict[str, Any] | None:
    headers: dict[str, str] = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in {b"\r\n", b"\n"}:
            break
        key, _, value = line.decode("ascii", "replace").partition(":")
        headers[key.lower()] = value.strip()
    length = int(headers.get("content-length", "0"))
    return json.loads(sys.stdin.buffer.read(length).decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Predicate MCP server")
    parser.add_argument("--policy", default="examples/policies/enterprise_ai.yml")
    parser.add_argument("--datahub-url")
    parser.add_argument("--datahub-file", help="Local DataHub-shaped graph for a safe smoke test")
    parser.add_argument("--token")
    args = parser.parse_args()
    server = PredicateMCP(args.policy, args.datahub_url, args.token, args.datahub_file)
    for request in iter(_read, None):
        method = request.get("method")
        request_id = request.get("id")
        if request_id is None:
            continue
        try:
            if method == "initialize":
                value = {
                    "protocolVersion": request.get("params", {}).get("protocolVersion", "2024-11-05"),
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "predicate", "version": "0.1.0"},
                }
            elif method == "tools/list":
                value = {"tools": TOOLS}
            elif method == "tools/call":
                params = request.get("params", {})
                value = server.call(params.get("name", ""), params.get("arguments", {}))
                value = _result(value)
            else:
                raise ValueError(f"unsupported method: {method}")
            _send({"jsonrpc": "2.0", "id": request_id, "result": value})
        except Exception as error:
            _send({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32000, "message": str(error)},
            })


if __name__ == "__main__":
    main()
