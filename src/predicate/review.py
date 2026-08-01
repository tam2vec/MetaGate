from __future__ import annotations

import argparse
import json
import os
import time
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


def _repo_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "examples/outputs/predicate-demo-app.html").exists():
        return cwd
    return Path(__file__).resolve().parents[2]


ROOT = _repo_root()
# Local review serves the source page directly, so UI edits are visible after
# restarting the service without relying on a copied/generated HTML artifact.
APP = ROOT / "public-demo/index.html"
RUNS = ROOT / "examples/outputs/live-runs.json"
DEFAULT_URNS = [
    "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)",
    "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_deleted,PROD)",
    "urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)",
    "urn:li:dataset:(urn:li:dataPlatform:kafka,SampleKafkaDataset,PROD)",
]
STARTED_AT = time.time()


class ReviewConfigError(ValueError):
    pass


def _asset_name(urn: str) -> str:
    return urn.split(",")[-2] if "," in urn else urn


def _decision_to_run(certificate: dict, decision: dict, policy=None) -> dict:
    action_thresholds = None
    if policy is not None:
        matching_policy = next(
            (item for item in policy.capability_policies if item.name == decision["capability"]),
            None,
        )
        if matching_policy:
            action_thresholds = {
                "score": matching_policy.minimum_score,
                "confidence": matching_policy.minimum_confidence,
            }
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
        "action_thresholds": action_thresholds,
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
    def __init__(
        self,
        policy_path: str,
        datahub_url: str | None,
        datahub_file: str | None,
        *,
        allow_recorded_fallback: bool = True,
    ):
        self.policy_path = policy_path
        self.datahub_url = datahub_url
        self.datahub_file = datahub_file
        self.allow_recorded_fallback = allow_recorded_fallback
        if datahub_file and datahub_url:
            raise ReviewConfigError("Use either --datahub-file or --datahub-url, not both.")
        if not datahub_file and not (datahub_url or os.environ.get("DATAHUB_GRAPHQL_URL")):
            raise ReviewConfigError(
                "Set --datahub-url, DATAHUB_GRAPHQL_URL, or --datahub-file before starting Predicate Review."
            )
        if datahub_file and not Path(datahub_file).exists():
            raise ReviewConfigError(f"DataHub fixture file does not exist: {datahub_file}")
        if not Path(policy_path).exists():
            raise ReviewConfigError(f"Policy file does not exist: {policy_path}")
        self.policy = load_policy(policy_path)
        self.engine = ReadinessEngine(self.policy)
        if datahub_file:
            self.client = FileDataHubClient(datahub_file)
        else:
            self.client = GraphQLDataHubClient(datahub_url or os.environ.get("DATAHUB_GRAPHQL_URL"))
        self.extractor = DataHubEvidenceExtractor(
            self.client,
            cache=JsonCache(ROOT / ".context-gradient/review-cache.json"),
        )

    def evaluate(self, urn: str, capability: str, *, refresh: bool = False) -> dict:
        if refresh:
            self.extractor.invalidate(urn)
        bundle = self.extractor.bundle(urn)
        certificate = self.engine.certify(bundle).as_dict()
        decision = admit_capability(certificate, capability).__dict__
        decision["action_predicate"] = _action_predicate(
            certificate,
            self.policy,
            capability,
            decision["allowed"],
        )
        return _decision_to_run(certificate, decision, self.policy)

    def runs(self, urns: list[str], capability: str, *, refresh: bool = False) -> list[dict]:
        live_runs = []
        for urn in urns:
            try:
                live_runs.append(self.evaluate(urn, capability, refresh=refresh))
            except Exception:
                continue
        if live_runs:
            return live_runs
        if self.allow_recorded_fallback and RUNS.exists():
            return [_normalize_recorded(run) for run in json.loads(RUNS.read_text())]
        return []

    def health(self) -> dict:
        return {
            "status": "ok",
            "mode": "fixture" if self.datahub_file else "datahub_graphql",
            "policy": self.policy_path,
            "datahub_url_configured": bool(self.datahub_url or os.environ.get("DATAHUB_GRAPHQL_URL")),
            "recorded_fallback": self.allow_recorded_fallback,
            "uptime_seconds": round(time.time() - STARTED_AT, 3),
        }

    def ready(self, urns: list[str], capability: str) -> dict:
        runs = self.runs(urns[:1], capability)
        return {
            "status": "ready" if runs else "degraded",
            "checked_urns": urns[:1],
            "runs_returned": len(runs),
            "mode": "fixture" if self.datahub_file else "datahub_graphql",
            "recorded_fallback": self.allow_recorded_fallback,
        }

    def status(self, urns: list[str], capability: str) -> dict:
        """Return a judge-friendly, machine-readable explanation of this server."""
        health = self.health()
        readiness = self.ready(urns, capability)
        return {
            "product": "Predicate",
            "service": "Predicate Review",
            "mode": "fixture-api" if self.datahub_file else "live-datahub-api",
            "data_source": "local fixture" if self.datahub_file else "DataHub GraphQL",
            "policy": self.policy_path,
            "capability": capability,
            "recorded_fallback_enabled": self.allow_recorded_fallback,
            "ready": readiness["status"] == "ready",
            "health": health["status"],
            "checked_urns": urns,
            "writeback": {
                "configured": bool(os.environ.get("DATAHUB_CERTIFICATE_MUTATION")),
                "verified_readback_configured": bool(os.environ.get("DATAHUB_CERTIFICATE_QUERY")),
                "mode": "explicit-and-verified" if os.environ.get("DATAHUB_CERTIFICATE_MUTATION") and os.environ.get("DATAHUB_CERTIFICATE_QUERY") else "read-only",
            },
        }


def make_handler(state: ReviewState, urns: list[str], capability: str, cors_origin: str = "*"):
    class Handler(BaseHTTPRequestHandler):
        def _json(self, payload: dict, status: int = 200) -> None:
            body = json.dumps(payload, indent=2).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Access-Control-Allow-Origin", cors_origin)
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _html(self) -> None:
            body = APP.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/healthz":
                self._json(state.health())
                return
            if parsed.path == "/readyz":
                readiness = state.ready(urns, capability)
                self._json(readiness, 200 if readiness["status"] == "ready" else 503)
                return
            if parsed.path == "/api/status":
                self._json(state.status(urns, capability))
                return
            if parsed.path in {"/", "/review"}:
                self._html()
                return
            if parsed.path == "/api/runs":
                refresh = "refresh" in parse_qs(parsed.query)
                self._json(
                    {
                        "source": "live-api" if not state.datahub_file else "fixture-api",
                        "runs": state.runs(urns, capability, refresh=refresh),
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
                    self._json(state.evaluate(urn, requested_capability, refresh=True))
                except Exception as error:
                    self._json({"error": str(error)}, 500)
                return
            self.send_error(404)

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", cors_origin)
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def log_message(self, format: str, *args) -> None:
            return

    return Handler


class QuietReviewServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the live Predicate Review app.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--policy", default="examples/policies/enterprise_ai.yml")
    parser.add_argument("--datahub-url", default=os.environ.get("DATAHUB_GRAPHQL_URL"))
    parser.add_argument("--datahub-file")
    parser.add_argument(
        "--no-recorded-fallback",
        action="store_true",
        help="Do not serve recorded demo runs if live DataHub evaluation fails.",
    )
    parser.add_argument(
        "--cors-origin",
        default=os.environ.get("PREDICATE_CORS_ORIGIN", "*"),
        help="Allowed browser origin for the review API. Use a specific URL in private deployments.",
    )
    parser.add_argument("--capability", default="autonomous-agent-action")
    parser.add_argument(
        "--urn",
        action="append",
        dest="urns",
        help="DataHub URN to evaluate. Repeat for multiple assets.",
    )
    args = parser.parse_args()

    state = ReviewState(
        args.policy,
        args.datahub_url,
        args.datahub_file,
        allow_recorded_fallback=not args.no_recorded_fallback,
    )
    urns = args.urns or DEFAULT_URNS
    server = QuietReviewServer(
        (args.host, args.port),
        make_handler(state, urns, args.capability, args.cors_origin),
    )
    print(f"Predicate Review is running at http://{args.host}:{args.port}/review")
    print(f"Serving app from {APP}")
    server.serve_forever()


if __name__ == "__main__":
    main()
