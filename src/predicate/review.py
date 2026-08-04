from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from context_gradient.cli import _action_predicate
from context_gradient.datahub.adapter import DataHubEvidenceExtractor, GraphQLDataHubClient

try:
    from context_gradient.datahub.adapter import DEFAULT_MAX_HOPS
except ImportError:
    # Keep older deployed adapters bootable while the repository is upgraded.
    # The next deployment must include adapter.py so live evidence semantics
    # match the review server.
    DEFAULT_MAX_HOPS = 1
from context_gradient.datahub.mock_client import FileDataHubClient
from context_gradient.sdk.admission import admit_capability
from context_gradient.sdk.cache import JsonCache
from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.history import ReadinessHistory
from context_gradient.sdk.policy import load_policy
from predicate.review_store import ReviewStore


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
    "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)",
    "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)",
    "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_deleted,PROD)",
    "urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)",
    "urn:li:dataset:(urn:li:dataPlatform:kafka,SampleKafkaDataset,PROD)",
    "urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.customer_lifetime_value,PROD)",
]
STARTED_AT = time.time()


class ReviewConfigError(ValueError):
    pass


def _asset_name(urn: str) -> str:
    return urn.split(",")[-2] if "," in urn else urn


def _decision_to_run(certificate: dict, decision: dict, policy=None) -> dict:
    capability_result = next(
        (
            item
            for item in certificate.get("certified_capabilities", [])
            if item.get("capability") == decision["capability"]
        ),
        None,
    )
    # The decision is capability-specific. Keep the overall certificate too,
    # but show the score that actually governed the selected action in the UI.
    overall_readiness = certificate.get("readiness_score")
    overall_confidence = certificate.get("confidence")
    action_readiness = capability_result.get("score") if capability_result else overall_readiness
    action_confidence = capability_result.get("confidence") if capability_result else overall_confidence
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
    score_trace = dict(certificate.get("metadata", {}).get("score_trace", {}))
    score_trace["displayed_capability"] = decision["capability"]
    score_trace["displayed_readiness_score"] = action_readiness
    score_trace["displayed_confidence"] = action_confidence
    return {
        "entity_urn": decision["entity_urn"],
        "urn": decision["entity_urn"],
        "asset": _asset_name(decision["entity_urn"]),
        "capability": decision["capability"],
        "allowed": decision["allowed"],
        "decision": "allowed" if decision["allowed"] else "blocked",
        "reason": decision["reason"],
        "readiness": action_readiness,
        "confidence": action_confidence,
        "readiness_score": action_readiness,
        "overall_readiness": overall_readiness,
        "overall_confidence": overall_confidence,
        "capability_score": action_readiness,
        "capability_confidence": action_confidence,
        "policy": certificate.get("metadata", {}).get("policy"),
        "evidence": decision.get("evidence", []),
        "gaps": certificate.get("gaps", []),
        "failed": decision.get("action_predicate", {}).get("failed_terms", []),
        "action_predicate": decision.get("action_predicate", {}),
        "predicate": decision.get("action_predicate", {}),
        "action_thresholds": action_thresholds,
        "score_trace": score_trace,
        "datahub_observation": certificate.get("metadata", {}).get("datahub_observation", {}),
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
        max_hops: int = DEFAULT_MAX_HOPS,
    ):
        self.policy_path = policy_path
        self.datahub_url = datahub_url
        self.datahub_file = datahub_file
        # Live mode must never silently display an older recorded decision.
        self.allow_recorded_fallback = bool(allow_recorded_fallback and datahub_file)
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
            # The review page needs direct lineage evidence for its decision.
            # Deeper graph walks belong in the evidence view and make every
            # refresh fan out into many extra GraphQL requests.
            max_hops=max_hops,
            # The cache filename is versioned so a scoring/rubric change can
            # never silently reuse an older evidence interpretation.
            cache=JsonCache(ROOT / ".context-gradient/review-cache-v4.json"),
        )
        self.assessment_history = ReadinessHistory(ROOT / ".context-gradient/assessment-history")
        self.review_store = ReviewStore(ROOT / ".context-gradient/review.sqlite3")
        self.last_errors: list[dict] = []

    def reviews(self, urn: str, capability: str) -> list[dict]:
        return self.review_store.reviews(urn, capability)

    def save_review(self, urn: str, capability: str, verdict: str, note: str, actor: str = "local-user") -> dict:
        if verdict not in {"agree", "disagree"}:
            raise ValueError("verdict must be agree or disagree")
        if not note.strip():
            raise ValueError("note is required")
        record = {
            "urn": urn,
            "capability": capability,
            "verdict": verdict,
            "note": note.strip(),
            "actor": actor.strip() or "local-user",
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        return self.review_store.add_review(record)

    def evaluate(self, urn: str, capability: str, *, refresh: bool = False) -> dict:
        if refresh:
            self.extractor.invalidate(urn)
        bundle = self.extractor.bundle(urn)
        certificate_obj = self.engine.certify(bundle)
        certificate = certificate_obj.as_dict()
        previous = self.assessment_history.latest(urn)
        self.assessment_history.append(certificate_obj)
        decision = admit_capability(certificate, capability).__dict__
        decision["action_predicate"] = _action_predicate(
            certificate,
            self.policy,
            capability,
            decision["allowed"],
        )
        run = _decision_to_run(certificate, decision, self.policy)
        run["assessment"] = certificate.get("metadata", {}).get("assessment", {})
        run["facts"] = run["assessment"].get("facts", {})
        run["guidance"] = run["assessment"].get("guidance", "")
        run["before_after"] = {
            "previous_readiness": previous.get("readiness_score") if previous else None,
            "current_readiness": run["readiness_score"],
            "readiness_delta": round(run["readiness_score"] - previous["readiness_score"], 2) if previous else None,
            "previous_confidence": previous.get("confidence") if previous else None,
            "current_confidence": run["confidence"],
            "confidence_delta": round(run["confidence"] - previous["confidence"], 2) if previous else None,
            "previous_gaps": [gap["evidence_kind"] for gap in (previous.get("gaps", []) if previous else [])],
            "current_gaps": [gap["evidence_kind"] for gap in run["gaps"]],
        }
        event = {
            "decision_id": f"pred-{int(time.time() * 1000)}",
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "decision": run["decision"],
            "capability": capability,
            "reason": run["reason"],
        }
        run["decision_id"] = event["decision_id"]
        run["evaluated_at"] = event["evaluated_at"]
        # Persist the complete evaluated run, including score, evidence,
        # before/after context, and predicate terms, not only the headline.
        self.review_store.record_decision(run)
        run["history"] = self.review_store.decisions(urn, capability, limit=10)
        override = self.review_store.latest_override(urn, capability)
        run["override"] = override
        run["effective_decision"] = override["decision"] if override else run["decision"]
        run["effective_allowed"] = run["effective_decision"] == "allowed"
        run["saved_assessments"] = [
            {
                "issued_at": item.get("issued_at"),
                "readiness_score": item.get("readiness_score"),
                "confidence": item.get("confidence"),
                "gap_count": len(item.get("gaps", [])),
            }
            for item in self.assessment_history.list(urn)
        ]
        return run

    def save_override(self, urn: str, capability: str, decision: str, reason: str, actor: str, role: str) -> dict:
        if role not in {"steward", "admin"}:
            raise PermissionError("Only a steward or admin may override a blocked decision.")
        if decision not in {"allowed", "blocked"}:
            raise ValueError("decision must be allowed or blocked")
        if not actor.strip() or not reason.strip():
            raise ValueError("actor and reason are required")
        return self.review_store.add_override({
            "urn": urn,
            "capability": capability,
            "decision": decision,
            "reason": reason.strip(),
            "actor": actor.strip(),
            "role": role,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    def runs(self, urns: list[str], capability: str, *, refresh: bool = False) -> list[dict]:
        live_runs = []
        self.last_errors = []
        # Each asset requires its own DataHub and lineage reads. Run those
        # independent checks together so one slow asset does not hold up the
        # entire review page.
        with ThreadPoolExecutor(max_workers=min(5, max(1, len(urns)))) as pool:
            futures = {
                pool.submit(self.evaluate, urn, capability, refresh=refresh): urn
                for urn in urns
            }
            results = {}
            for future in as_completed(futures):
                urn = futures[future]
                try:
                    results[urn] = future.result()
                except Exception as error:
                    self.last_errors.append({"urn": urn, "error": str(error)})
        # Keep every configured asset visible. A failed DataHub read must not
        # make the asset disappear or make the run count look healthier than it
        # is; represent it explicitly as unavailable instead.
        live_runs = []
        for urn in urns:
            if urn in results:
                live_runs.append(results[urn])
                continue
            error = next((item["error"] for item in self.last_errors if item["urn"] == urn), "Unknown DataHub error.")
            live_runs.append({
                "asset": _asset_name(urn),
                "urn": urn,
                "decision": "unavailable",
                "allowed": False,
                "readiness_score": None,
                "confidence": None,
                "reason": f"Predicate could not evaluate this asset: {error}",
                "evidence": [],
                "failed": [],
                "error": error,
                "action_predicate": {"decision": "unavailable", "result": None, "failed_terms": []},
            })
        if live_runs:
            return live_runs
        # Recorded runs are acceptable for an explicitly fixture-backed demo,
        # but never mask a failed live DataHub read. A stale recorded card is
        # worse than an honest error when the score is used for admission.
        if self.allow_recorded_fallback and self.datahub_file and RUNS.exists():
            return [_normalize_recorded(run) for run in json.loads(RUNS.read_text())]
        return []

    def health(self) -> dict:
        live = not self.datahub_file
        return {
            "status": "ok",
            "mode": "fixture" if self.datahub_file else "datahub_graphql",
            "live_datahub": live,
            "policy": self.policy_path,
            "datahub_url_configured": bool(self.datahub_url or os.environ.get("DATAHUB_GRAPHQL_URL")),
            "datahub_token_configured": bool(os.environ.get("DATAHUB_TOKEN")),
            "recorded_fallback": self.allow_recorded_fallback,
            "fixture_fallback_blocked": live and not self.allow_recorded_fallback,
            "uptime_seconds": round(time.time() - STARTED_AT, 3),
            "history_store": "sqlite",
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
        return {
            "product": "Predicate",
            "service": "Predicate Review",
            "mode": "fixture-api" if self.datahub_file else "live-datahub-api",
            "data_source": "local fixture" if self.datahub_file else "DataHub GraphQL",
            "live_datahub": not self.datahub_file,
            "datahub_url_configured": health["datahub_url_configured"],
            "datahub_token_configured": health["datahub_token_configured"],
            "fixture_fallback_blocked": not self.datahub_file and not self.allow_recorded_fallback,
            "policy": self.policy_path,
            "capability": capability,
            "recorded_fallback_enabled": self.allow_recorded_fallback,
            "ready": health["status"] == "ok",
            "health": health["status"],
            "checked_urns": urns,
            "writeback": {
                "configured": bool(os.environ.get("DATAHUB_CERTIFICATE_MUTATION")),
                "verified_readback_configured": bool(os.environ.get("DATAHUB_CERTIFICATE_QUERY")),
                "mode": "explicit-and-verified" if os.environ.get("DATAHUB_CERTIFICATE_MUTATION") and os.environ.get("DATAHUB_CERTIFICATE_QUERY") else "read-only",
            },
            "evaluation_errors": self.last_errors,
            "rbac": {
                "evaluation": "requester or reviewer",
                "review_notes": "requester or reviewer",
                "overrides": "steward or admin only",
                "override_reason_required": True,
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
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
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
                # A live API request must always reflect current DataHub
                # metadata. This also protects older browser tabs whose JS
                # still requests /api/runs without the refresh query flag.
                refresh = bool(state.datahub_url) or "refresh" in parse_qs(parsed.query)
                self._json(
                    {
                        "source": "live-api" if not state.datahub_file else "fixture-api",
                        "runs": state.runs(urns, capability, refresh=refresh),
                        "errors": state.last_errors,
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
            if parsed.path == "/api/history":
                query = parse_qs(parsed.query)
                urn = query.get("urn", [""])[0]
                capability_name = query.get("capability", [capability])[0]
                if not urn:
                    self._json({"error": "Missing urn query parameter."}, 400)
                    return
                self._json({
                    "urn": urn,
                    "capability": capability_name,
                    "assessments": state.assessment_history.list(urn, limit=25),
                    "decisions": state.review_store.decisions(urn, capability_name, limit=25),
                })
                return
            if parsed.path == "/api/reviews":
                query = parse_qs(parsed.query)
                urn = query.get("urn", [""])[0]
                capability_name = query.get("capability", [capability])[0]
                if not urn:
                    self._json({"error": "Missing urn query parameter."}, 400)
                    return
                self._json({"urn": urn, "capability": capability_name, "reviews": state.reviews(urn, capability_name)})
                return
            if parsed.path == "/api/overrides":
                query = parse_qs(parsed.query)
                urn = query.get("urn", [""])[0]
                capability_name = query.get("capability", [capability])[0]
                if not urn:
                    self._json({"error": "Missing urn query parameter."}, 400)
                    return
                self._json({
                    "urn": urn,
                    "capability": capability_name,
                    "override": state.review_store.latest_override(urn, capability_name),
                })
                return
            self.send_error(404)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path not in {"/api/reviews", "/api/overrides"}:
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode() or "{}")
                if parsed.path == "/api/overrides":
                    self.do_POST_override(payload)
                    return
                urn = str(payload.get("urn", "")).strip()
                if not urn:
                    raise ValueError("urn is required")
                record = state.save_review(
                    urn,
                    str(payload.get("capability", capability)),
                    str(payload.get("verdict", "")),
                    str(payload.get("note", "")),
                    str(payload.get("actor") or self.headers.get("X-Predicate-Actor", "local-user")),
                )
                self._json({"review": record}, 201)
            except PermissionError as error:
                self._json({"error": str(error)}, 403)
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                self._json({"error": str(error)}, 400)

        def do_POST_override(self, payload: dict) -> None:
            urn = str(payload.get("urn", "")).strip()
            if not urn:
                raise ValueError("urn is required")
            actor = str(payload.get("actor") or self.headers.get("X-Predicate-Actor", "")).strip()
            role = str(payload.get("role") or self.headers.get("X-Predicate-Role", "requester")).strip().lower()
            record = state.save_override(
                urn,
                str(payload.get("capability", capability)),
                str(payload.get("decision", "")),
                str(payload.get("reason", "")),
                actor,
                role,
            )
            self._json({"override": record}, 201)

        def do_OPTIONS(self) -> None:
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", cors_origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
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
    # Leave this unset when --datahub-file is used. ReviewState can still read
    # DATAHUB_GRAPHQL_URL for live mode, but a fixture must not be rejected
    # merely because the shell happens to retain a live endpoint variable.
    parser.add_argument("--datahub-url")
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
        "--max-hops",
        type=int,
        default=DEFAULT_MAX_HOPS,
        help="Lineage graph scope. Keep this equal to the CLI --max-hops value.",
    )
    parser.add_argument(
        "--urn",
        action="append",
        dest="urns",
        help="DataHub URN to evaluate. Repeat for multiple assets.",
    )
    args = parser.parse_args()

    demo_mode = os.environ.get("PREDICATE_DEMO_MODE", "").strip().lower()
    if demo_mode not in {"", "fixture", "live"}:
        raise ReviewConfigError("PREDICATE_DEMO_MODE must be 'fixture' or 'live'.")
    if demo_mode == "live":
        # Hosted live mode must be explicit and fail closed. In particular, a
        # missing endpoint must never turn into a convincing fixture page.
        if args.datahub_file:
            raise ReviewConfigError("PREDICATE_DEMO_MODE=live cannot use --datahub-file.")
        if not (args.datahub_url or os.environ.get("DATAHUB_GRAPHQL_URL")):
            raise ReviewConfigError(
                "PREDICATE_DEMO_MODE=live requires DATAHUB_GRAPHQL_URL or --datahub-url."
            )
        args.no_recorded_fallback = True

    state = ReviewState(
        args.policy,
        args.datahub_url,
        args.datahub_file,
        allow_recorded_fallback=not args.no_recorded_fallback,
        max_hops=args.max_hops,
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
