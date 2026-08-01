from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from context_gradient.cli import _action_predicate
from context_gradient.datahub.adapter import DataHubEvidenceExtractor, GraphQLDataHubClient
from context_gradient.datahub.mock_client import FileDataHubClient
from context_gradient.sdk.admission import admit_capability
from context_gradient.sdk.cache import JsonCache
from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.policy import load_policy


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "examples/outputs/predicate-demo-app.html"
RUNS = ROOT / "examples/outputs/live-runs.json"
DEFAULT_URNS = [
    "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)",
    "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_deleted,PROD)",
    "urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)",
    "urn:li:dataset:(urn:li:dataPlatform:kafka,SampleKafkaDataset,PROD)",
]


def _asset_name(urn: str) -> str:
    return urn.split(",")[-2] if "," in urn else urn


def _decision_to_run(certificate: dict, decision: dict) -> dict:
    return {
        "entity_urn": decision["entity_urn"],
        "urn": decision["entity_urn"],
        "asset": _asset_name(decision["entity_urn"]),
        "capability": decision["capability"],
        "allowed": decision["allowed"],
        "decision": "allowed" if decision["allowed"] else "blocked",
        "reason": decision["reason"],
        "readiness": certificate.get("readiness_score"),
        "confidence": certificate.get("confidence"),
        "readiness_score": certificate.get("readiness_score"),
        "policy": certificate.get("metadata", {}).get("policy"),
        "evidence": decision.get("evidence", []),
        "failed": decision.get("action_predicate", {}).get("failed_terms", []),
        "action_predicate": decision.get("action_predicate", {}),
        "predicate": decision.get("action_predicate", {}),
    }


def _normalize_recorded(run: dict) -> dict:
    predicate = run.get("action_predicate") or run.get("predicate") or {}
    readiness = run.get("readiness", run.get("readiness_score"))
    return {
        **run,
        "urn": run.get("urn") or run.get("entity_urn"),
        "readiness": readiness,
        "readiness_score": run.get("readiness_score", readiness),
        "failed": run.get("failed", predicate.get("failed_terms", [])),
        "predicate": predicate,
    }


class ReviewState:
    def __init__(self, policy_path: str, datahub_url: str | None, datahub_file: str | None):
        self.policy_path = policy_path
        self.datahub_url = datahub_url
        self.datahub_file = datahub_file
        self.policy = load_policy(policy_path)
        self.engine = ReadinessEngine(self.policy)
        if datahub_file:
            self.client = FileDataHubClient(datahub_file)
        else:
            self.client = GraphQLDataHubClient(datahub_url or os.environ.get("DATAHUB_GRAPHQL_URL"))
        self.extractor = DataHubEvidenceExtractor(self.client, cache=JsonCache(ROOT / ".context-gradient/review-cache.json"))

    def evaluate(self, urn: str, capability: str) -> dict:
        bundle = self.extractor.bundle(urn)
        certificate = self.engine.certify(bundle).as_dict()
        decision = admit_capability(certificate, capability).__dict__
        decision["action_predicate"] = _action_predicate(certificate, self.policy, capability, decision["allowed"])
        return _decision_to_run(certificate, decision)

    def runs(self, urns: list[str], capability: str) -> list[dict]:
        live_runs = []
        for urn in urns:
            try:
                live_runs.append(self.evaluate(urn, capability))
            except Exception:
                continue
        if live_runs:
            return live_runs
        if RUNS.exists():
            return [_normalize_recorded(run) for run in json.loads(RUNS.read_text())]
        return []


def make_handler(state: ReviewState, urns: list[str], capability: str):
    class Handler(BaseHTTPRequestHandler):
        def _json(self, payload: dict, status: int = 200) -> None:
            body = json.dumps(payload, indent=2).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _html(self) -> None:
            body = APP.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/review"}:
                self._html()
                return
            if parsed.path == "/api/runs":
                self._json(
                    {
                        "source": "live-api" if not state.datahub_file else "fixture-api",
                        "runs": state.runs(urns, capability),
                    }
                )
                return
            if parsed.path == "/api/evaluate":
                query = parse_qs(parsed.query)
                urn = query.get("urn", [""])[0]
                requested_capability = query.get("capability", [capability])[0]
                if not urn:
                    self._json({"error": "Missing urn query parameter."}, 400)
                    return
                try:
                    self._json(state.evaluate(urn, requested_capability))
                except Exception as error:
                    self._json({"error": str(error)}, 500)
                return
            self.send_error(404)

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def log_message(self, format: str, *args) -> None:
            return

    return Handler


class QuietReviewServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address) -> None:
        # Browsers can reset file/API requests while refreshing or navigating.
        # Keep the demo terminal clean unless the server itself exits.
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the live Predicate Review app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--policy", default="examples/policies/enterprise_ai.yml")
    parser.add_argument("--datahub-url", default=os.environ.get("DATAHUB_GRAPHQL_URL"))
    parser.add_argument("--datahub-file")
    parser.add_argument("--capability", default="autonomous-agent-action")
    parser.add_argument("--urn", action="append", dest="urns", help="DataHub URN to evaluate. Repeat for multiple assets.")
    args = parser.parse_args()

    state = ReviewState(args.policy, args.datahub_url, args.datahub_file)
    urns = args.urns or DEFAULT_URNS
    server = QuietReviewServer((args.host, args.port), make_handler(state, urns, args.capability))
    print(f"Predicate Review is running at http://{args.host}:{args.port}/review")
    server.serve_forever()


if __name__ == "__main__":
    main()
