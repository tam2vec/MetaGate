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
from context_gradient.sdk.admission import enforce_action_guardrails
from context_gradient.sdk.cache import JsonCache
from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.history import ReadinessHistory
from context_gradient.sdk.policy import load_policy
from predicate.review_store import ReviewStore
from predicate.hackathon_resources import resource_catalog
from predicate.contracts import build_constraint_contract


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
# Visible in /api/status so a stale Render image cannot masquerade as the
# current repository. Bump this when the judge-visible service changes.
BUILD_ID = os.environ.get("PREDICATE_BUILD_ID", "predicate-six-asset-proof-v2")


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
    normalized = {
        **run,
        "urn": run.get("urn") or run.get("entity_urn"),
        "readiness": readiness,
        "readiness_score": run.get("readiness_score", readiness),
        "failed": run.get("failed", predicate.get("failed_terms", [])),
        "predicate": predicate,
    }
    if not normalized.get("constraint_contract"):
        normalized["constraint_contract"] = build_constraint_contract(normalized, normalized.get("capability"))
    return normalized


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
        # Resolve the endpoint once. If it comes from DATAHUB_GRAPHQL_URL,
        # live runs must still bypass the evidence cache.
        resolved_datahub_url = datahub_url or os.environ.get("DATAHUB_GRAPHQL_URL")
        self.datahub_url = None if datahub_file else resolved_datahub_url
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
            self.client = GraphQLDataHubClient(
                datahub_url or os.environ.get("DATAHUB_GRAPHQL_URL"),
                token=os.environ.get("DATAHUB_TOKEN"),
            )
        self.extractor = DataHubEvidenceExtractor(
            self.client,
            # The review page needs direct lineage evidence for its decision.
            # Deeper graph walks belong in the evidence view and make every
            # refresh fan out into many extra GraphQL requests.
            max_hops=max_hops,
            # A live DataHub is the source of truth. Caching live evidence can
            # show yesterday's score after metadata changes, so only fixture
            # mode gets the fast local cache.
            cache=(JsonCache(ROOT / ".context-gradient/review-cache-v4.json") if datahub_file else None),
        )
        self.assessment_history = ReadinessHistory(ROOT / ".context-gradient/assessment-history")
        self.review_store = ReviewStore(ROOT / ".context-gradient/review.sqlite3")
        self.last_errors: list[dict] = []
        self.discovery_error: str | None = None

    def resolve_urns(
        self,
        configured_urns: list[str],
        *,
        discover_assets: bool = False,
        max_assets: int = 1000,
    ) -> list[str]:
        """Choose the assets for this run without hiding catalog failures.

        Live review uses the connected DataHub catalog as its scope, while
        retaining explicitly configured proof assets. This matters for the
        hackathon demo: a newly loaded catalog may not contain every curated
        example yet, but those examples should remain visible as unavailable
        rather than silently disappearing from the review.
        """
        self.discovery_error = None
        if not discover_assets:
            # The CLI supplies DEFAULT_URNS when no explicit --urn is given,
            # but callers of the state object may pass an empty list directly.
            # Keep both entry points on the same six-asset proof scope.
            return list(configured_urns or DEFAULT_URNS)
        try:
            discovered = list(self.client.list_dataset_urns())
        except Exception as exc:
            self.discovery_error = str(exc)
            return [] if not self.datahub_file else list(configured_urns)
        if not discovered:
            self.discovery_error = "DataHub returned no dataset URNs. Load metadata, then refresh Predicate."
            return list(configured_urns[:max_assets])
        # Keep the explicit proof set first, then append the live catalog.
        # De-duplication preserves order so the six-asset demo is stable while
        # still allowing a larger connected DataHub catalog to be explored.
        merged = list(dict.fromkeys([*configured_urns, *discovered]))
        return merged[:max_assets]

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
        decision = enforce_action_guardrails(certificate, capability).__dict__
        decision["action_predicate"] = _action_predicate(
            certificate,
            self.policy,
            capability,
            decision["allowed"],
            decision.get("reason"),
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
        run["constraint_contract"] = build_constraint_contract(run, capability)
        run["saved"] = True
        run["saved_source"] = "review-server-sqlite"
        override = self.review_store.latest_override(urn, capability)
        run["override"] = override
        run["effective_decision"] = override["decision"] if override else run["decision"]
        run["effective_allowed"] = run["effective_decision"] == "allowed"
        # Overrides change the enforcement boundary, so persist and return a
        # contract that reflects the effective decision rather than the stale
        # pre-override verdict.
        run["constraint_contract"] = build_constraint_contract(run, capability)
        # Persist the complete evaluated run, including score, evidence,
        # before/after context, and predicate terms, but never its derived
        # history list. ReviewStore strips that field defensively as well.
        self.review_store.record_decision(run)
        run["history"] = self.review_store.decisions(urn, capability, limit=10)
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

    def integration_proof(self, urn: str, capability: str) -> dict:
        """Prove the agent-facing entry points agree on one asset.

        The Skill and Predicate MCP adapter deliberately share the extractor,
        policy, and guardrails. This endpoint makes that agreement visible to
        a judge without claiming that DataHub's separate official MCP server
        was invoked when it has not been configured here.
        """
        if not urn:
            raise ValueError("urn is required")
        source = {
            "mode": "fixture" if self.datahub_file else "live-datahub",
            "datahub_url_configured": bool(self.datahub_url),
            "token_configured": bool(os.environ.get("DATAHUB_TOKEN")),
            "fixture": self.datahub_file,
        }
        result: dict = {
            "product": "Predicate",
            "asset": urn,
            "capability": capability,
            "source": source,
            "skill": {"entrypoint": "context_gradient.skill.certify"},
            "predicate_mcp": {"tool": "predicate_evaluate"},
            "official_datahub_mcp": {},
        }
        try:
            from predicate.datahub_mcp_probe import probe_datahub_mcp

            result["official_datahub_mcp"] = probe_datahub_mcp(urn)
        except Exception as error:
            result["official_datahub_mcp"] = {
                "status": "attention_required",
                "error": str(error),
                "note": "The optional official DataHub MCP probe could not be started.",
            }
        official_entity_call = result["official_datahub_mcp"].get("entity_call") or {}
        # Keep the processed MCP facts easy for API consumers to inspect. The
        # official MCP remains an optional, read-only evidence source and is
        # never silently merged into the GraphQL evaluation below.
        result["official_mcp_evidence"] = official_entity_call.get("evidence", {})
        result["official_mcp_facts"] = official_entity_call.get("facts", {})
        result["official_mcp_query"] = result["official_datahub_mcp"].get("query_call", {})
        try:
            from context_gradient.skill import certify

            skill = certify(
                urn,
                self.policy_path,
                datahub_url=self.datahub_url,
                datahub_file=self.datahub_file,
                capability=capability,
            )
            result["skill"].update({
                "status": "ok",
                "decision": skill.get("decision"),
                "decision_id": skill.get("decision_id"),
                "contract_version": (skill.get("constraint_contract") or {}).get("contract_version"),
                "evidence": (skill.get("constraint_contract") or {}).get("evidence", {}),
            })
        except Exception as error:
            result["skill"].update({"status": "error", "error": str(error)})
        try:
            from predicate.mcp_server import PredicateMCP

            mcp = PredicateMCP(
                self.policy_path,
                self.datahub_url,
                os.environ.get("DATAHUB_TOKEN"),
                self.datahub_file,
            )
            mcp_result = mcp.evaluate({"urn": urn, "capability": capability})
            result["predicate_mcp"].update({
                "status": "ok",
                "decision": mcp_result.get("decision"),
                "decision_id": mcp_result.get("decision_id"),
                "contract_version": (mcp_result.get("constraint_contract") or {}).get("contract_version"),
                "evidence": (mcp_result.get("constraint_contract") or {}).get("evidence", {}),
            })
        except Exception as error:
            result["predicate_mcp"].update({"status": "error", "error": str(error)})
        skill_result = result["skill"]
        mcp_result = result["predicate_mcp"]
        result["same_asset"] = True
        result["same_decision"] = (
            skill_result.get("status") == "ok"
            and mcp_result.get("status") == "ok"
            and skill_result.get("decision") == mcp_result.get("decision")
        )
        skill_evidence = (skill_result.get("evidence") or {})
        mcp_evidence = (mcp_result.get("evidence") or {})
        # The two entry points run at different instants, so observation
        # timestamps and generated decision IDs are expected to differ. The
        # proof compares the evidence state and the underlying latest facts,
        # not volatile bookkeeping fields.
        def comparable_evidence(value: dict) -> dict:
            comparable = {}
            for key, item in value.items():
                if not isinstance(item, dict):
                    comparable[key] = item
                    continue
                comparable[key] = {
                    field: field_value
                    for field, field_value in item.items()
                    if field not in {"observed_at", "decision_id"}
                }
            return comparable

        result["evidence_agreement"] = comparable_evidence(skill_evidence) == comparable_evidence(mcp_evidence)
        result["status"] = (
            "verified"
            if result["same_asset"] and result["same_decision"] and result["evidence_agreement"]
            else "attention_required"
        )
        return result

    def runs(
        self,
        urns: list[str],
        capability: str,
        *,
        refresh: bool = False,
        include_saved: bool = False,
    ) -> list[dict]:
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
            unavailable_run = {
                "asset": _asset_name(urn),
                "urn": urn,
                "entity_urn": urn,
                "capability": capability,
                "decision": "unavailable",
                "allowed": False,
                "readiness_score": None,
                "confidence": None,
                "reason": f"Predicate could not evaluate this asset: {error}",
                "evidence": [],
                "failed": [],
                "error": error,
                "action_predicate": {"decision": "unavailable", "result": None, "failed_terms": []},
                "decision_id": f"pred-unavailable-{int(time.time() * 1000)}",
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "datahub_observation": {"status": "unavailable", "error": error},
            }
            unavailable_run["constraint_contract"] = build_constraint_contract(unavailable_run, capability)
            live_runs.append(unavailable_run)

        # A dataset checked through /api/evaluate may not be part of the
        # server's startup scope. Keep its latest saved evaluation visible on
        # the review page after refreshes and server restarts. Current assets
        # win over saved copies so a live DataHub failure is never hidden by
        # an older result for the same URN.
        if include_saved:
            current_urn_set = set(urns)
            visible_urns = {run.get("urn") or run.get("entity_urn") for run in live_runs}
            for saved_run in self.review_store.latest_runs(capability):
                saved_urn = saved_run.get("urn") or saved_run.get("entity_urn")
                if not saved_urn or saved_urn in current_urn_set or saved_urn in visible_urns:
                    continue
                saved_run = _normalize_recorded(dict(saved_run))
                saved_run["saved"] = True
                saved_run["saved_source"] = "review-server-sqlite"
                saved_run["stale_until_rechecked"] = True
                live_runs.append(saved_run)
                visible_urns.add(saved_urn)

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

    def resources(self) -> dict:
        """Return hackathon profiles plus the real datasets in this source."""
        discovered = []
        error = None
        try:
            discovered = self.client.list_dataset_urns()
        except Exception as exc:
            error = str(exc)
        return {
            "resources": resource_catalog(),
            "discovered_dataset_urns": discovered,
            "discovery_error": error,
            "source": "fixture" if self.datahub_file else "live-datahub",
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
        configured_urns = list(DEFAULT_URNS)
        available_urns = []
        if self.datahub_file:
            try:
                available_urns = list(self.client.list_dataset_urns())
            except Exception:
                available_urns = []
        missing_configured = [urn for urn in configured_urns if urn not in set(available_urns)] if self.datahub_file else []
        return {
            "product": "Predicate",
            "service": "Predicate Review",
            "build_id": BUILD_ID,
            "repository_version": "0.1.0",
            "mode": "fixture-api" if self.datahub_file else "live-datahub-api",
            "data_source": "local fixture" if self.datahub_file else "DataHub GraphQL",
            "live_datahub": not self.datahub_file,
            "datahub_url_configured": health["datahub_url_configured"],
            "datahub_token_configured": health["datahub_token_configured"],
            "fixture_fallback_blocked": not self.datahub_file and not self.allow_recorded_fallback,
            "policy": self.policy_path,
            "capability": capability,
            "configured_asset_count": len(configured_urns),
            "resolved_asset_count": len(urns),
            "configured_assets": configured_urns,
            "resolved_assets": urns,
            "missing_configured_assets": missing_configured,
            "asset_scope": "six-asset proof fixture" if self.datahub_file else "connected DataHub catalog plus configured proof assets",
            "recorded_fallback_enabled": self.allow_recorded_fallback,
            "ready": health["status"] == "ok",
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


def make_handler(
    state: ReviewState,
    urns: list[str],
    capability: str,
    cors_origin: str = "*",
    *,
    discover_assets: bool = False,
    max_assets: int = 1000,
):
    def current_urns() -> list[str]:
        return state.resolve_urns(
            urns,
            discover_assets=discover_assets,
            max_assets=max_assets,
        )

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
                readiness = state.ready(current_urns(), capability)
                self._json(readiness, 200 if readiness["status"] == "ready" else 503)
                return
            if parsed.path == "/api/status":
                self._json(state.status(current_urns(), capability))
                return
            if parsed.path == "/api/resources":
                resources = state.resources()
                resources["auto_scoring_enabled"] = discover_assets
                resources["max_assets_per_run"] = max_assets
                self._json(resources)
                return
            if parsed.path in {"/", "/review"}:
                self._html()
                return
            if parsed.path == "/api/runs":
                # A live API request must always reflect current DataHub
                # metadata. This also protects older browser tabs whose JS
                # still requests /api/runs without the refresh query flag.
                refresh = bool(state.datahub_url) or "refresh" in parse_qs(parsed.query)
                run_urns = current_urns()
                evaluated_runs = state.runs(run_urns, capability, refresh=refresh, include_saved=True)
                evaluated_urns = {run.get("urn") or run.get("entity_urn") for run in evaluated_runs}
                self._json(
                    {
                        "source": "live-api" if not state.datahub_file else "fixture-api",
                        "runs": evaluated_runs,
                        "errors": state.last_errors,
                        "discovered": discover_assets,
                        "asset_count": len(run_urns),
                        "configured_asset_count": len(urns),
                        "build_id": BUILD_ID,
                        "asset_scope": "connected DataHub catalog" if discover_assets else "configured URN list",
                        "missing_configured_assets": [configured for configured in urns if configured not in evaluated_urns]
                        if state.datahub_file else [],
                        "discovery_error": state.discovery_error,
                    }
                )
                return
            if parsed.path == "/api/saved-runs":
                query = parse_qs(parsed.query)
                capability_name = query.get("capability", [capability])[0]
                self._json({
                    "source": "review-server-sqlite",
                    "capability": capability_name,
                    "runs": state.review_store.latest_runs(capability_name),
                })
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
            if parsed.path == "/api/integration-proof":
                query = parse_qs(parsed.query)
                urn = query.get("urn", [""])[0]
                requested_capability = query.get("capability", [capability])[0]
                if not urn:
                    self._json({"error": "Missing urn query parameter."}, 400)
                    return
                try:
                    self._json(state.integration_proof(urn, requested_capability))
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
        "--discover-assets",
        action="store_true",
        help="Discover and score dataset URNs from the connected DataHub on every run refresh.",
    )
    parser.add_argument(
        "--max-assets",
        type=int,
        default=int(os.environ.get("PREDICATE_MAX_ASSETS", "1000")),
        help="Maximum discovered dataset assets to score per refresh (default: 1000).",
    )
    parser.add_argument(
        "--urn",
        action="append",
        dest="urns",
        help="DataHub URN to evaluate. Repeat for multiple assets.",
    )
    args = parser.parse_args()
    if args.max_assets < 1:
        raise ReviewConfigError("--max-assets must be at least 1.")

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
        make_handler(
            state,
            urns,
            args.capability,
            args.cors_origin,
            discover_assets=args.discover_assets,
            max_assets=args.max_assets,
        ),
    )
    print(f"Predicate Review is running at http://{args.host}:{args.port}/review")
    print(f"Serving app from {APP}")
    if args.discover_assets:
        print(f"Automatic DataHub asset discovery enabled (up to {args.max_assets} datasets per refresh).")
    server.serve_forever()


if __name__ == "__main__":
    main()
