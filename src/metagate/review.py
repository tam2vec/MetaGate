from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from context_gradient.cli import _action_metagate
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
from metagate.review_store import ReviewStore
from metagate.hackathon_resources import annotate_scenario_resources, resource_catalog
from metagate.contracts import build_constraint_contract
from metagate.incident_investigator import investigate
from metagate.datahub_action import handle_action
from metagate.datahub_mcp_probe import probe_datahub_mcp
from metagate.agent_gate import ToolCallDenied, guarded_tool_call
from metagate.agent_registry import (
    DEFAULT_AGENT_URN,
    DEFAULT_SERVICE_URN,
    DEFAULT_SKILL_URN,
    DEFAULT_TOOL_URN,
    apply_agent_registry_gate,
    resolve_agent_context,
)
from metagate.adversarial_scenarios import CATEGORIES, generate_scenarios
from metagate.repair_proof import run_fixture_repair_proof


def _repo_root() -> Path:
    cwd = Path.cwd()
    if (cwd / "examples/outputs/metagate-demo-app.html").exists():
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
STARTED_AT_ISO = datetime.now(timezone.utc).isoformat()
# Visible in /api/status so a stale Render image cannot masquerade as the
# current repository. Bump this when the judge-visible service changes.
BUILD_ID = os.environ.get("METAGATE_BUILD_ID", "metagate-catalog-first-v1")
RUNTIME_ROOT = Path(os.environ.get("METAGATE_RUNTIME_ROOT", str(ROOT))).resolve()
SOURCE_ROOT = Path(os.environ.get("METAGATE_SOURCE_ROOT", str(ROOT))).resolve()
WRITEBACK_RECEIPT = Path(
    os.environ.get(
        "METAGATE_WRITEBACK_RECEIPT",
        str(RUNTIME_ROOT / ".context-gradient/writeback-receipt.json"),
    )
).resolve()


def runtime_identity() -> dict:
    """Identify the process serving the page without exposing credentials."""
    return {
        "build_id": BUILD_ID,
        "pid": os.getpid(),
        "started_at": STARTED_AT_ISO,
        "runtime_root": str(RUNTIME_ROOT),
        "source_root": str(SOURCE_ROOT),
        "runtime_mode": "source" if RUNTIME_ROOT == SOURCE_ROOT else "synced-copy",
        "source_path": str(Path(__file__).resolve()),
        "app_path": str(APP.resolve()),
    }


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
        "failed": decision.get("action_metagate", {}).get("failed_terms", []),
        "action_metagate": decision.get("action_metagate", {}),
        "metagate": decision.get("action_metagate", {}),
        "action_thresholds": action_thresholds,
        # Preserve the capability-specific evidence contract. The review UI,
        # CLI, and enforcement API must agree on what was required and what
        # DataHub actually returned for the selected action.
        "required_evidence": capability_result.get("required_evidence", []) if capability_result else [],
        "evidence_status": capability_result.get("evidence_status", {}) if capability_result else {},
        "certified_capabilities": certificate.get("certified_capabilities", []),
        "score_trace": score_trace,
        "datahub_observation": certificate.get("metadata", {}).get("datahub_observation", {}),
    }


def _normalize_recorded(run: dict) -> dict:
    metagate = run.get("action_metagate") or run.get("metagate") or {}
    readiness = run.get("readiness", run.get("readiness_score"))
    normalized = {
        **run,
        "urn": run.get("urn") or run.get("entity_urn"),
        "readiness": readiness,
        "readiness_score": run.get("readiness_score", readiness),
        "failed": run.get("failed", metagate.get("failed_terms", [])),
        "metagate": metagate,
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
        registry_path: str | None = None,
        agent_id: str | None = None,
        skill_id: str | None = None,
        tool_id: str | None = None,
        service_id: str | None = None,
        require_agent_registry: bool = False,
        catalog_first: bool | None = None,
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
        live_source = bool(self.datahub_url) and not datahub_file
        if catalog_first is None:
            catalog_first = live_source
        if catalog_first and datahub_file:
            raise ReviewConfigError("Catalog-first mode requires --datahub-url, not --datahub-file.")
        if not datahub_file and not (datahub_url or os.environ.get("DATAHUB_GRAPHQL_URL")):
            raise ReviewConfigError(
                "Set --datahub-url, DATAHUB_GRAPHQL_URL, or --datahub-file before starting MetaGate Review."
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
            # A live DataHub remains the source of truth. The extractor keeps
            # only a short-lived process-local bundle so switching capabilities
            # does not repeat the same GraphQL fan-out; explicit refresh still
            # invalidates it. Durable JSON caching remains fixture-only.
            cache=(JsonCache(ROOT / ".context-gradient/review-cache-v4.json") if datahub_file else None),
        )
        self.assessment_history = ReadinessHistory(ROOT / ".context-gradient/assessment-history")
        self.review_store = ReviewStore(ROOT / ".context-gradient/review.sqlite3")
        self.registry_path = registry_path
        self.agent_id = agent_id
        self.skill_id = skill_id
        self.tool_id = tool_id
        self.service_id = service_id
        self.require_agent_registry = bool(require_agent_registry)
        self.catalog_first = bool(catalog_first and not datahub_file)
        # The official DataHub MCP server is optional because many local
        # deployments do not have it installed. When configured, its proof is
        # attached to every decision rather than living only in a side page.
        self.official_mcp_command = os.environ.get("METAGATE_DATAHUB_MCP_COMMAND", "").strip()
        self.require_official_mcp = os.environ.get("METAGATE_REQUIRE_OFFICIAL_MCP", "").strip().lower() in {
            "1", "true", "yes"
        }
        self.last_errors: list[dict] = []
        self.discovery_error: str | None = None
        # Catalog refreshes can involve hundreds or thousands of independent
        # DataHub reads. Keep them off the request thread so the review page
        # can render the latest saved decision immediately.
        self._refresh_executor = ThreadPoolExecutor(max_workers=1)
        self._refresh_lock = threading.RLock()
        self._refresh_running = False
        self._refresh_started_at: str | None = None
        self._refresh_completed_at: str | None = None
        self._refresh_error: str | None = None
        self._refresh_total = 0
        self._refresh_completed = 0
        self._refresh_scope: list[str] = []

    def refresh_status(self) -> dict:
        with self._refresh_lock:
            return {
                "running": self._refresh_running,
                "started_at": self._refresh_started_at,
                "completed_at": self._refresh_completed_at,
                "error": self._refresh_error,
                "total": self._refresh_total,
                "completed": self._refresh_completed,
                "scope_urns": list(self._refresh_scope),
                "progress": (
                    round(self._refresh_completed / self._refresh_total, 3)
                    if self._refresh_total else 0
                ),
            }

    def start_background_refresh(
        self,
        configured_urns: list[str],
        capability: str,
        *,
        discover_assets: bool,
        max_assets: int,
    ) -> dict:
        """Start one catalog refresh without making the browser wait for it."""
        with self._refresh_lock:
            if self._refresh_running:
                return self.refresh_status()
            self._refresh_running = True
            self._refresh_started_at = datetime.now(timezone.utc).isoformat()
            self._refresh_completed_at = None
            self._refresh_error = None
            self._refresh_total = 0
            self._refresh_completed = 0
            self._refresh_scope = []
        self._refresh_executor.submit(
            self._background_refresh,
            list(configured_urns),
            capability,
            discover_assets,
            max_assets,
        )
        return self.refresh_status()

    def _background_refresh(
        self,
        configured_urns: list[str],
        capability: str,
        discover_assets: bool,
        max_assets: int,
    ) -> None:
        try:
            scope = self.resolve_urns(
                configured_urns,
                discover_assets=discover_assets,
                max_assets=max_assets,
            )
            with self._refresh_lock:
                self._refresh_scope = list(scope)
                self._refresh_total = len(scope)
            # runs() persists each completed decision to SQLite. A later
            # request therefore sees progressively newer results even while
            # the catalog is still being processed.
            evaluated = self.runs(
                scope,
                capability,
                refresh=True,
                include_saved=False,
                progress_callback=self._record_refresh_progress,
            )
            with self._refresh_lock:
                self._refresh_completed = len(evaluated)
        except Exception as error:
            with self._refresh_lock:
                self._refresh_error = str(error)
        finally:
            with self._refresh_lock:
                self._refresh_running = False
                self._refresh_completed_at = datetime.now(timezone.utc).isoformat()

    def _record_refresh_progress(self, completed: int) -> None:
        with self._refresh_lock:
            self._refresh_completed = completed

    def _official_mcp(self, urn: str) -> dict:
        if not self.official_mcp_command:
            return {
                "status": "not_configured",
                "server": "DataHub official MCP server",
                "checked_urn": urn,
                "trace": [],
                "note": "Set METAGATE_DATAHUB_MCP_COMMAND to the approved official DataHub MCP startup command.",
            }
        try:
            return probe_datahub_mcp(urn, self.official_mcp_command)
        except Exception as error:
            return {
                "status": "attention_required",
                "server": "DataHub official MCP server",
                "checked_urn": urn,
                "trace": [],
                "error": str(error),
                "note": "The configured official MCP server could not be verified.",
            }

    def resolve_urns(
        self,
        configured_urns: list[str],
        *,
        discover_assets: bool = False,
        max_assets: int = 0,
    ) -> list[str]:
        """Choose the assets for this run without hiding catalog failures.

        Catalog-first live mode treats DataHub's dataset search as the source
        of truth. The fixed proof assets are only a fixture/demo fallback and
        must never be injected into a real catalog scan.
        """
        self.discovery_error = None
        configured_scope = list(configured_urns or DEFAULT_URNS)
        requested_limit = int(max_assets)
        # Zero (and negative values for compatibility with older launchers)
        # means every dataset returned by DataHub. A positive value is an
        # explicit safety cap for very large catalogs.
        limit = None if requested_limit <= 0 else min(requested_limit, 10000)
        if not discover_assets:
            return [] if self.catalog_first else configured_scope
        try:
            discovered = list(self.client.list_dataset_urns())
        except Exception as exc:
            self.discovery_error = str(exc)
            return [] if self.catalog_first else list(configured_scope[:len(configured_scope) if limit is None else max(limit, len(configured_scope))])
        if not discovered:
            self.discovery_error = "DataHub returned no dataset URNs. Load metadata, then refresh MetaGate."
            return [] if self.catalog_first else list(configured_scope[:len(configured_scope) if limit is None else max(limit, len(configured_scope))])
        unique_discovered = list(dict.fromkeys(discovered))
        if self.catalog_first:
            return unique_discovered if limit is None else unique_discovered[:limit]
        # Fixture/legacy mode keeps the explicit proof set first, then appends
        # discovered assets. This preserves the deterministic demo contract.
        merged = list(dict.fromkeys([*configured_scope, *unique_discovered]))
        legacy_limit = len(configured_scope) if limit is None else max(limit, len(configured_scope))
        return merged[:legacy_limit]

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

    def _reuse_saved_evidence(self, urn: str, capability: str) -> dict | None:
        """Reframe the latest asset evidence for a capability without a new read.

        The review page uses this only for a capability switch. A manual
        refresh and all machine-facing default evaluations still read DataHub.
        The response is labelled so a caller cannot mistake it for a fresh
        observation.
        """
        if self.datahub_file:
            return None
        saved = self.review_store.latest_decision_for_urn(urn)
        if not saved:
            return None
        capability_result = next(
            (
                item
                for item in saved.get("certified_capabilities", [])
                if isinstance(item, dict) and item.get("capability") == capability
            ),
            None,
        )
        if not capability_result:
            return None
        run = deepcopy(saved)
        allowed = bool(capability_result.get("certified", capability_result.get("allowed", False)))
        evidence_status = dict(capability_result.get("evidence_status") or {})
        failed_terms = [
            f"{kind}.present"
            for kind, status in evidence_status.items()
            if str(status).lower() not in {"present", "clear", "complete"}
        ]
        if str(evidence_status.get("incidents", "")).lower() in {"open", "open_incident"}:
            failed_terms.append("incidents.open == 0")
        reasons = capability_result.get("reasons") or []
        run.update(
            {
                "capability": capability,
                "allowed": allowed,
                "decision": "allowed" if allowed else "blocked",
                "effective_allowed": allowed,
                "effective_decision": "allowed" if allowed else "blocked",
                "readiness": capability_result.get("score"),
                "readiness_score": capability_result.get("score"),
                "capability_score": capability_result.get("score"),
                "confidence": capability_result.get("confidence"),
                "capability_confidence": capability_result.get("confidence"),
                "reason": "Capability is certified by the active policy." if allowed else "; ".join(map(str, reasons)),
                "failed": list(dict.fromkeys(failed_terms)),
                "failed_terms": list(dict.fromkeys(failed_terms)),
                "required_evidence": capability_result.get("required_evidence", []),
                "evidence_status": evidence_status,
                "evaluation_mode": "saved_evidence_reuse",
                "stale_until_rechecked": True,
                "saved_source": "review-server-sqlite",
            }
        )
        matching_policy = next(
            (item for item in self.policy.capability_policies if item.name == capability),
            None,
        )
        if matching_policy:
            run["action_thresholds"] = {
                "score": matching_policy.minimum_score,
                "confidence": matching_policy.minimum_confidence,
            }
        run["action_metagate"] = {
            "action": capability,
            "result": allowed,
            "decision": run["decision"],
            "failed_terms": run["failed"],
        }
        run["metagate"] = run["action_metagate"]
        override = self.review_store.latest_override(urn, capability)
        run["override"] = override
        if override:
            run["effective_decision"] = override["decision"]
            run["effective_allowed"] = override["decision"] == "allowed"
        run["constraint_contract"] = build_constraint_contract(run, capability)
        return run

    def evaluate(self, urn: str, capability: str, *, refresh: bool = False) -> dict:
        has_memory_bundle = getattr(self.extractor, "has_memory_bundle", lambda _urn: False)(urn)
        if not refresh and not has_memory_bundle:
            reused = self._reuse_saved_evidence(urn, capability)
            if reused:
                return reused
        if refresh:
            self.extractor.invalidate(urn)
        bundle = self.extractor.bundle(urn)
        certificate_obj = self.engine.certify(bundle)
        certificate = certificate_obj.as_dict()
        previous = self.assessment_history.latest(urn)
        self.assessment_history.append(certificate_obj)
        decision = enforce_action_guardrails(certificate, capability).__dict__
        decision["action_metagate"] = _action_metagate(
            certificate,
            self.policy,
            capability,
            decision["allowed"],
            decision.get("reason"),
        )
        run = _decision_to_run(certificate, decision, self.policy)
        agent_context = resolve_agent_context(
            registry_path=self.registry_path,
            dataset_urn=urn,
            agent_id=self.agent_id,
            skill_id=self.skill_id,
            tool_id=self.tool_id,
            service_id=self.service_id,
            requested=self.require_agent_registry,
            capability=capability,
        )
        run["registry_required"] = self.require_agent_registry
        run["agent_context"] = agent_context
        run["registry_evidence"] = agent_context
        if self.require_agent_registry:
            apply_agent_registry_gate(run, agent_context, capability)
            run["allowed"] = bool(run.get("allowed")) and run.get("decision") == "allowed"
            run["failed"] = run.get("action_metagate", {}).get("failed_terms", [])
            run["failed_terms"] = list(run["failed"])
        run["assessment"] = certificate.get("metadata", {}).get("assessment", {})
        run["facts"] = run["assessment"].get("facts", {})
        run["guidance"] = run["assessment"].get("guidance", "")
        run["incident_investigation"] = investigate(run)
        official_mcp = self._official_mcp(urn)
        run["official_datahub_mcp"] = official_mcp
        run["official_mcp_evidence"] = (official_mcp.get("entity_call") or {}).get("evidence", {})
        run["official_mcp_facts"] = (official_mcp.get("entity_call") or {}).get("facts", {})
        run["official_mcp_query"] = official_mcp.get("query_call", {})
        run["mcp_trace"] = official_mcp.get("trace", [])
        run["mcp_gate"] = {
            "required": self.require_official_mcp,
            "status": official_mcp.get("status", "attention_required"),
            "decision_effect": "blocking" if self.require_official_mcp else "informational",
        }
        if self.require_official_mcp and official_mcp.get("status") != "verified":
            run["allowed"] = False
            run["decision"] = "blocked"
            run["reason"] = (run.get("reason", "") + "; " if run.get("reason") else "") + (
                "Official DataHub MCP evidence could not be verified"
            )
            run["failed"] = list(dict.fromkeys([*(run.get("failed") or []), "official_datahub_mcp.verified"]))
            run["failed_terms"] = list(run["failed"])
            run["action_metagate"] = _action_metagate(
                certificate,
                self.policy,
                capability,
                False,
                run["reason"],
            )
            run["metagate"] = run["action_metagate"]
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
        # before/after context, and metagate terms, but never its derived
        # history list. ReviewStore strips that field defensively as well.
        self.review_store.record_decision(run)
        self.review_store.add_audit_event({
            "urn": urn,
            "decision_id": run["decision_id"],
            "event_type": "decision_evaluated",
            "payload": {
                "capability": capability,
                "decision": run["effective_decision"],
                "readiness": run["readiness_score"],
                "confidence": run["confidence"],
                "failed_terms": run.get("failed", []),
                "incident_investigation": run["incident_investigation"],
            },
            "created_at": run["evaluated_at"],
        })
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

        The Skill and MetaGate MCP adapter deliberately share the extractor,
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
            "product": "MetaGate",
            "asset": urn,
            "capability": capability,
            "source": source,
            "skill": {"entrypoint": "context_gradient.skill.certify"},
            "metagate_mcp": {"tool": "metagate_evaluate"},
            "official_datahub_mcp": {},
        }
        live_run = self.evaluate(urn, capability, refresh=True)
        result["agent_registry"] = live_run.get("agent_context") or {
            "status": "not_requested",
            "source": "agent-registry-not-configured",
            "evidence": [],
            "blocking_reasons": [],
        }
        # evaluate() already ran the configured official MCP probe and attached
        # it to the same decision. Reuse that result so the proof page cannot
        # show a second, different MCP observation.
        result["official_datahub_mcp"] = live_run.get("official_datahub_mcp") or self._official_mcp(urn)
        result["mcp_trace"] = result["official_datahub_mcp"].get("trace", [])
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
            from metagate.mcp_server import MetaGateMCP

            mcp = MetaGateMCP(
                self.policy_path,
                self.datahub_url,
                os.environ.get("DATAHUB_TOKEN"),
                self.datahub_file,
            )
            mcp_result = mcp.evaluate({"urn": urn, "capability": capability})
            result["metagate_mcp"].update({
                "status": "ok",
                "decision": mcp_result.get("decision"),
                "decision_id": mcp_result.get("decision_id"),
                "contract_version": (mcp_result.get("constraint_contract") or {}).get("contract_version"),
                "evidence": (mcp_result.get("constraint_contract") or {}).get("evidence", {}),
            })
        except Exception as error:
            result["metagate_mcp"].update({"status": "error", "error": str(error)})
        skill_result = result["skill"]
        mcp_result = result["metagate_mcp"]
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
        progress_callback=None,
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
                if progress_callback is not None:
                    progress_callback(len(results) + len(self.last_errors))
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
                "reason": f"MetaGate could not evaluate this asset: {error}",
                "evidence": [],
                "failed": [],
                "error": error,
                "action_metagate": {"decision": "unavailable", "result": None, "failed_terms": []},
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
            live_runs.extend(self.saved_runs(capability, exclude_urns=urns))

        if live_runs:
            return live_runs
        # Recorded runs are acceptable for an explicitly fixture-backed demo,
        # but never mask a failed live DataHub read. A stale recorded card is
        # worse than an honest error when the score is used for admission.
        if self.allow_recorded_fallback and self.datahub_file and RUNS.exists():
            return [_normalize_recorded(run) for run in json.loads(RUNS.read_text())]
        return []

    def saved_runs(self, capability: str, *, exclude_urns: list[str] | set[str] = ()) -> list[dict]:
        """Return persisted checks that are outside the current evaluation scope.

        Saved history is useful after a restart, but it is not fresh DataHub
        evidence. Keep the distinction in the response so consumers cannot
        mistake an older check for a current catalog result.
        """
        excluded = set(exclude_urns)
        saved = []
        for record in self.review_store.latest_runs(capability):
            saved_urn = record.get("urn") or record.get("entity_urn")
            if not saved_urn or saved_urn in excluded:
                continue
            saved_run = _normalize_recorded(dict(record))
            saved_run["saved"] = True
            saved_run["saved_source"] = "review-server-sqlite"
            saved_run["stale_until_rechecked"] = True
            saved.append(saved_run)
        return saved

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
            "runtime": runtime_identity(),
        }

    def resources(self) -> dict:
        """Return hackathon profiles plus the real datasets in this source."""
        discovered = []
        error = None
        try:
            discovered = self.client.list_dataset_urns()
        except Exception as exc:
            error = str(exc)
        resources = annotate_scenario_resources(resource_catalog(), discovered)
        scenarios = [item for item in resources if item.get("kind") == "scenario"]
        return {
            "resources": resources,
            "discovered_dataset_urns": discovered,
            "discovery_error": error,
            "scenario_summary": {
                "loaded": sum(1 for item in scenarios if item.get("reviewable")),
                "total": len(scenarios),
            },
            "source": "fixture" if self.datahub_file else "live-datahub",
        }

    def adversarial_proof(self) -> dict:
        scenarios = generate_scenarios()
        return {
            "status": "synthetic-proof-set",
            "scenario_count": len(scenarios),
            "categories": list(CATEGORIES),
            "independent_human_labels": False,
            "note": "Generated adversarial cases exercise the gate; they are not external accuracy labels.",
            "scenarios": scenarios,
        }

    def repair_proof(self) -> dict:
        return run_fixture_repair_proof()

    def evidence(self, urn: str, capability: str, *, refresh: bool = True) -> dict:
        """Return the canonical evidence-first response for one evaluation.

        The UI can summarize this payload, while agents can consume it without
        reverse-engineering score fields.  In particular, unavailable evidence
        is kept separate from evidence that is genuinely absent.
        """
        if not urn:
            raise ValueError("urn is required")
        run = self.evaluate(urn, capability, refresh=refresh)
        contract = run.get("constraint_contract") or build_constraint_contract(run, capability)
        facts = run.get("facts") or run.get("assessment", {}).get("facts", {}) or {}
        compact = contract.get("evidence") or {}
        unavailable = sorted(
            key for key, value in compact.items()
            if isinstance(value, dict) and value.get("status") == "unavailable"
        )
        absent = sorted(
            key for key, value in compact.items()
            if isinstance(value, dict) and value.get("status") in {"absent", "incomplete", "stale", "partial"}
        )
        return {
            "product": "MetaGate",
            "asset": run.get("asset"),
            "entity_urn": urn,
            "capability": capability,
            "decision": run.get("effective_decision", run.get("decision")),
            "allowed": bool(run.get("effective_allowed", run.get("allowed"))),
            "decision_id": run.get("decision_id"),
            "evaluated_at": run.get("evaluated_at"),
            "source": run.get("datahub_observation") or {
                "mode": "fixture" if self.datahub_file else "datahub_graphql",
                "url_configured": bool(self.datahub_url),
            },
            "evidence": compact,
            "facts": facts,
            "evidence_used": run.get("evidence", []),
            "blocking_reasons": contract.get("blocking_reasons", []),
            "unavailable_evidence": unavailable,
            "absent_or_unusable_evidence": absent,
            "next_step": contract.get("next_step"),
            "constraint_contract": contract,
            "incident_investigation": run.get("incident_investigation", {}),
            "before_after": run.get("before_after", {}),
            "score_note": "Scores summarize the decision; current evidence and blocking reasons are authoritative.",
        }

    def scan(self, configured_urns: list[str], capability: str, *, limit: int = 0, refresh: bool = True) -> dict:
        """Evaluate the connected catalog, or the deterministic fixture scope."""
        requested_limit = int(limit)
        limit = 0 if requested_limit <= 0 else min(requested_limit, 10000)
        configured = [] if self.catalog_first else list(configured_urns or DEFAULT_URNS)
        scope = self.resolve_urns(configured, discover_assets=True, max_assets=limit)
        evaluated = self.runs(scope, capability, refresh=refresh, include_saved=False)
        saved = [] if self.catalog_first and not scope else self.saved_runs(capability, exclude_urns=scope)
        scope_set = set(scope)
        configured_set = set(configured)
        return {
            "product": "MetaGate",
            "source": "fixture-api" if self.datahub_file else "live-datahub-api",
            "mode": "fixture" if self.datahub_file else "datahub_graphql",
            "capability": capability,
            "asset_scope": "all connected DataHub datasets" if self.catalog_first else "configured proof assets plus connected DataHub catalog",
            "scope_mode": "catalog-first" if self.catalog_first else "additive",
            "catalog_authoritative": self.catalog_first,
            "catalog_available": bool(scope) if self.catalog_first else True,
            "configured_asset_count": len(configured),
            "catalog_asset_count": len(scope) if self.catalog_first else 0,
            "discovered_asset_count": len(scope_set) if self.catalog_first else len(scope_set - configured_set),
            "asset_count": len(evaluated),
            "current_scope_count": len(evaluated),
            "saved_run_count": len(saved),
            "limit": limit,
            "discovery_error": self.discovery_error,
            "errors": self.last_errors,
            "build_id": BUILD_ID,
            "runtime": runtime_identity(),
            "scope_integrity": {
                "configured_assets_retained": True if self.catalog_first else configured_set.issubset(scope_set),
                "configured_assets": configured,
                "missing_configured_assets": [] if self.catalog_first else [urn for urn in configured if urn not in scope_set],
                "discovery_is_additive": not self.catalog_first,
                "catalog_authoritative": self.catalog_first,
            },
            "runs": evaluated,
            "saved_runs": saved,
        }

    def enforcement_demo(self, urn: str) -> dict:
        """Show that MetaGate is an enforcement boundary, not only a report."""
        actions = [
            "answer-business-questions",
            "generate-executive-metrics",
            "modify-dataset",
            "restricted-sql",
        ]
        results = []
        for action in actions:
            run = self.evaluate(urn, action, refresh=True)
            contract = run.get("constraint_contract") or build_constraint_contract(run, action)
            invoked = False

            def marker() -> dict:
                nonlocal invoked
                invoked = True
                return {"executed": True}

            try:
                tool_result = guarded_tool_call(
                    contract,
                    action=action,
                    dataset_urn=urn,
                    tool=marker,
                    columns=[],
                    tool_urn=self.tool_id or DEFAULT_TOOL_URN,
                    service_urn=self.service_id or DEFAULT_SERVICE_URN,
                )
                results.append({
                    "action": action,
                    "decision": run.get("effective_decision", run.get("decision")),
                    "allowed": True,
                    "tool_called": invoked,
                    "tool_result": tool_result,
                    "decision_id": run.get("decision_id"),
                })
            except ToolCallDenied as error:
                results.append({
                    "action": action,
                    "decision": run.get("effective_decision", run.get("decision")),
                    "allowed": False,
                    "tool_called": invoked,
                    "tool_not_invoked": not invoked,
                    "error": str(error),
                    "decision_id": run.get("decision_id"),
                    "blocking_reasons": contract.get("blocking_reasons", []),
                })
        return {
            "product": "MetaGate",
            "asset": urn,
            "status": "verified-local-enforcement-demo",
            "note": "The marker tool is invoked only after the contract authorizes the action.",
            "results": results,
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

    def writeback_status(self) -> dict:
        """Report configured mutation separately from verified local proof."""
        mutation_configured = bool(os.environ.get("DATAHUB_CERTIFICATE_MUTATION"))
        readback_configured = bool(os.environ.get("DATAHUB_CERTIFICATE_QUERY"))
        verified_writeback = None
        if WRITEBACK_RECEIPT.exists():
            try:
                receipt_payload = json.loads(WRITEBACK_RECEIPT.read_text())
                receipt = receipt_payload.get("writeback", {})
                if receipt.get("verified_readback"):
                    verified_writeback = {
                        "verified_readback": True,
                        "asset": receipt.get("urn"),
                        "property": receipt.get("property_name"),
                        "transport": receipt.get("transport"),
                        "written_at": receipt.get("written_at"),
                        "read_back_at": receipt.get("read_back_at"),
                    }
            except (OSError, ValueError, TypeError):
                verified_writeback = None
        return {
            "configured": mutation_configured or verified_writeback is not None,
            "verified_readback_configured": readback_configured or verified_writeback is not None,
            "verified": verified_writeback is not None,
            "receipt": verified_writeback,
            "mode": (
                "verified-local-rest"
                if verified_writeback is not None and not (mutation_configured and readback_configured)
                else "explicit-and-verified"
                if mutation_configured and readback_configured
                else "read-only"
            ),
            "reason": (
                "Verified local REST write-back and read-back are recorded for the listed asset. "
                "Deployment-specific GraphQL mutation configuration is still separate."
                if verified_writeback is not None and not (mutation_configured and readback_configured)
                else "Write-back is read-only until a deployment-approved mutation and read-back query are configured. "
                "This local DataHub currently has token authentication disabled, so MetaGate cannot verify mutation authorization."
                if not (mutation_configured and readback_configured)
                else "Mutation and read-back query are configured; run the verification command before calling this live write-back."
            ),
        }

    def status(
        self,
        urns: list[str],
        capability: str,
        configured_urns: list[str] | None = None,
    ) -> dict:
        """Return a judge-friendly, machine-readable explanation of this server."""
        health = self.health()
        # Report the same scope used by /api/runs. Previously this endpoint
        # always described the six built-in proof assets even when the active
        # server was configured with a different set or discovered catalog.
        configured_urns = [] if self.catalog_first else list(configured_urns or urns or DEFAULT_URNS)
        available_urns = []
        if self.datahub_file:
            try:
                available_urns = list(self.client.list_dataset_urns())
            except Exception:
                available_urns = []
        missing_configured = [urn for urn in configured_urns if urn not in set(available_urns)] if self.datahub_file else []
        return {
            "product": "MetaGate",
            "service": "MetaGate Review",
            "build_id": BUILD_ID,
            "runtime": runtime_identity(),
            "repository_version": "0.1.0",
            "mode": "fixture-api" if self.datahub_file else "live-datahub-api",
            "data_source": "local fixture" if self.datahub_file else "DataHub GraphQL",
            "live_datahub": not self.datahub_file,
            "datahub_url_configured": health["datahub_url_configured"],
            "datahub_token_configured": health["datahub_token_configured"],
            "agent_registry": {
                "required": self.require_agent_registry,
                "source": self.registry_path or "metagate-local-agent-registry",
                # resolve_agent_context uses these same defaults when the
                # caller enables the registry gate without passing IDs.
                # Keep status truthful so the visible proof never disagrees
                # with the contract that actually enforced the decision.
                "agent_urn": self.agent_id or DEFAULT_AGENT_URN,
                "skill_urn": self.skill_id or DEFAULT_SKILL_URN,
                "tool_urn": self.tool_id or DEFAULT_TOOL_URN,
                "service_urn": self.service_id or DEFAULT_SERVICE_URN,
                "enforcement": "fail-closed tool gate" if self.require_agent_registry else "optional evidence",
            },
            "fixture_fallback_blocked": not self.datahub_file and not self.allow_recorded_fallback,
            "policy": self.policy_path,
            "capability": capability,
            "configured_asset_count": len(configured_urns),
            "resolved_asset_count": len(urns),
            "configured_assets": configured_urns,
            "resolved_assets": urns,
            "catalog_asset_count": len(urns) if self.catalog_first else 0,
            "catalog_available": bool(urns) if self.catalog_first else True,
            "catalog_authoritative": self.catalog_first,
            "scope_mode": "catalog-first" if self.catalog_first else "fixture-proof" if self.datahub_file else "configured",
            "discovery_error": self.discovery_error,
            "missing_configured_assets": missing_configured,
            "scope_integrity": {
                "configured_assets_retained": True if self.catalog_first else set(configured_urns).issubset(set(urns)),
                "configured_assets": configured_urns,
                "missing_configured_assets": [] if self.catalog_first else [urn for urn in configured_urns if urn not in set(urns)],
                "discovery_is_additive": not self.catalog_first,
                "catalog_authoritative": self.catalog_first,
            },
            "asset_scope": (
                f"fixture: {Path(self.datahub_file).name}"
                if self.datahub_file
                else "all datasets in connected DataHub catalog"
                if self.catalog_first
                else "connected DataHub catalog plus configured proof assets"
            ),
            "recorded_fallback_enabled": self.allow_recorded_fallback,
            "ready": health["status"] == "ok",
            "checked_urns": urns,
            "writeback": self.writeback_status(),
            "evaluation_errors": self.last_errors,
            "refresh": self.refresh_status(),
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
    max_assets: int = 0,
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

        def do_HEAD(self) -> None:
            """Support health probes and browser HEAD requests honestly."""
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/review"}:
                body = APP.read_bytes()
                content_type = "text/html; charset=utf-8"
                status = 200
            elif parsed.path in {"/healthz", "/readyz", "/api/status"}:
                if parsed.path == "/healthz":
                    payload = state.health()
                    status = 200
                elif parsed.path == "/readyz":
                    readiness = state.ready(current_urns(), capability)
                    payload = readiness
                    status = 200 if readiness["status"] == "ready" else 503
                else:
                    payload = state.status(current_urns(), capability, urns)
                    status = 200
                body = json.dumps(payload, indent=2).encode()
                content_type = "application/json"
            else:
                self.send_error(404)
                return
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Access-Control-Allow-Origin", cors_origin)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()

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
                self._json(state.status(current_urns(), capability, urns))
                return
            if parsed.path == "/api/resources":
                resources = state.resources()
                resources["auto_scoring_enabled"] = discover_assets
                resources["max_assets_per_run"] = max_assets
                self._json(resources)
                return
            if parsed.path == "/api/adversarial-scenarios":
                self._json(state.adversarial_proof())
                return
            if parsed.path == "/api/repair-proof":
                self._json(state.repair_proof())
                return
            if parsed.path == "/api/evidence":
                query = parse_qs(parsed.query)
                urn = query.get("urn", [""])[0]
                requested_capability = query.get("capability", [capability])[0]
                if not urn:
                    self._json({"error": "Missing urn query parameter."}, 400)
                    return
                try:
                    self._json(state.evidence(urn, requested_capability, refresh=True))
                except Exception as error:
                    self._json({"error": f"MetaGate could not read evidence: {error}"}, 503)
                return
            if parsed.path == "/api/scan":
                query = parse_qs(parsed.query)
                requested_capability = query.get("capability", [capability])[0]
                try:
                    limit = int(query.get("limit", [max_assets])[0])
                except (TypeError, ValueError):
                    limit = max_assets
                refresh_value = query.get("refresh", ["true"])[0].lower()
                refresh = refresh_value not in {"0", "false", "no"}
                try:
                    self._json(state.scan(urns, requested_capability, limit=limit, refresh=refresh))
                except Exception as error:
                    self._json({"error": f"MetaGate could not scan the connected catalog: {error}"}, 503)
                return
            if parsed.path == "/api/enforcement-demo":
                query = parse_qs(parsed.query)
                urn = query.get("urn", [""])[0]
                if not urn:
                    self._json({"error": "Missing urn query parameter."}, 400)
                    return
                try:
                    self._json(state.enforcement_demo(urn))
                except Exception as error:
                    self._json({"error": f"MetaGate could not run the enforcement demo: {error}"}, 503)
                return
            if parsed.path in {"/", "/review"}:
                self._html()
                return
            if parsed.path == "/api/runs":
                query = parse_qs(parsed.query)
                wait_value = query.get("wait", ["0"])[0].lower()
                wait_for_refresh = wait_value in {"1", "true", "yes"}
                requested_refresh = "refresh" in query
                # Live catalog refreshes are deliberately asynchronous. The
                # browser gets the last persisted decisions now, then polls
                # this endpoint while the worker re-checks DataHub.
                if state.datahub_url and not wait_for_refresh:
                    refresh_status = state.refresh_status()
                    # A newly started service has no persisted scope yet. The
                    # old behavior returned saved results with an empty
                    # catalog, leaving the UI stuck at zero assets until a
                    # manual refresh. Start the first catalog scan
                    # automatically; explicit refreshes still restart it.
                    needs_initial_catalog_scan = (
                        state.catalog_first
                        and not refresh_status.get("running")
                        and not refresh_status.get("scope_urns")
                        and not refresh_status.get("error")
                    )
                    refresh_info = state.start_background_refresh(
                        urns,
                        capability,
                        discover_assets=discover_assets,
                        max_assets=max_assets,
                    ) if requested_refresh or needs_initial_catalog_scan else refresh_status
                    saved_runs = state.saved_runs(capability)
                    run_urns = refresh_info.get("scope_urns", []) or state.refresh_status().get("scope_urns", [])
                    current_runs = []
                    evaluated_runs = saved_runs
                    current_scope_count = len(saved_runs)
                else:
                    refresh = requested_refresh or wait_for_refresh
                    run_urns = current_urns()
                    current_runs = state.runs(run_urns, capability, refresh=refresh, include_saved=False)
                    saved_runs = [] if state.catalog_first and not run_urns else state.saved_runs(capability, exclude_urns=run_urns)
                    evaluated_runs = current_runs + saved_runs
                    current_scope_count = len(current_runs)
                evaluated_urns = {run.get("urn") or run.get("entity_urn") for run in current_runs}
                configured_scope = [] if state.catalog_first else list(urns or DEFAULT_URNS)
                self._json(
                    {
                        "source": "live-api" if not state.datahub_file else "fixture-api",
                        "runs": evaluated_runs,
                        "saved_runs": saved_runs,
                        "errors": state.last_errors,
                        "discovered": discover_assets,
                        "asset_count": len(evaluated_runs),
                        "current_scope_count": current_scope_count,
                        "saved_run_count": len(saved_runs),
                        "scope_urns": run_urns,
                        "configured_asset_count": len(configured_scope),
                        "catalog_asset_count": len(run_urns) if state.catalog_first else 0,
                        "catalog_available": bool(run_urns) if state.catalog_first and not state.refresh_status()["running"] else True,
                        "catalog_authoritative": state.catalog_first,
                        "scope_mode": "catalog-first" if state.catalog_first else "additive",
                        "build_id": BUILD_ID,
                        "runtime": runtime_identity(),
                        "asset_scope": (
                            "all connected DataHub datasets plus saved checks"
                            if state.catalog_first and saved_runs
                            else "all connected DataHub datasets"
                            if state.catalog_first
                            else "connected DataHub catalog plus saved checks"
                            if discover_assets and saved_runs
                            else "connected DataHub catalog"
                            if discover_assets
                            else "configured URN list plus saved checks"
                            if saved_runs
                            else "configured URN list"
                        ),
                        "missing_configured_assets": [] if state.catalog_first else [configured for configured in configured_scope if configured not in evaluated_urns],
                        "scope_integrity": {
                            "configured_assets_retained": True if state.catalog_first else set(configured_scope).issubset(set(run_urns)),
                            "configured_assets": configured_scope,
                            "missing_configured_assets": [] if state.catalog_first else [configured for configured in configured_scope if configured not in set(run_urns)],
                            "discovery_is_additive": not state.catalog_first,
                            "catalog_authoritative": state.catalog_first,
                        },
                        "discovery_error": state.discovery_error,
                        "refresh": state.refresh_status(),
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
                refresh_value = query.get("refresh", ["true"])[0].lower()
                refresh = refresh_value not in {"0", "false", "no"}
                if not urn:
                    self._json({"error": "Missing urn query parameter."}, 400)
                    return
                try:
                    self._json(state.evaluate(urn, requested_capability, refresh=refresh))
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
            if parsed.path == "/api/audit-events":
                query = parse_qs(parsed.query)
                urn = query.get("urn", [""])[0]
                decision_id = query.get("decision_id", [None])[0]
                if not urn:
                    self._json({"error": "Missing urn query parameter."}, 400)
                    return
                self._json({
                    "urn": urn,
                    "decision_id": decision_id,
                    "events": state.review_store.audit_events(urn, decision_id),
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
            if parsed.path not in {"/api/reviews", "/api/overrides", "/api/datahub-action", "/api/tool-call"}:
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode() or "{}")
                if parsed.path == "/api/datahub-action":
                    result = handle_action(
                        payload,
                        lambda urn, requested_capability: state.evaluate(
                            urn, requested_capability, refresh=True
                        ),
                    )
                    self._json(result, 200)
                    return
                if parsed.path == "/api/tool-call":
                    urn = str(payload.get("dataset_urn") or payload.get("urn") or "").strip()
                    action = str(payload.get("action") or payload.get("capability") or "").strip()
                    if not urn or not action:
                        raise ValueError("dataset_urn and action are required")
                    run = state.evaluate(urn, action, refresh=True)
                    contract = run.get("constraint_contract") or build_constraint_contract(run, action)
                    tool_result = guarded_tool_call(
                        contract,
                        action=action,
                        dataset_urn=urn,
                        columns=payload.get("columns"),
                        human_approval=payload.get("human_approval"),
                        tool_urn=payload.get("tool_urn"),
                        service_urn=payload.get("service_urn"),
                        tool=lambda: {"executed": True, "action": action, "dataset_urn": urn},
                    )
                    self._json({
                        "tool_call": tool_result,
                        "decision": run,
                        "enforcement": "tool_invoked_after_metagate_allow",
                    }, 200)
                    return
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
                    str(payload.get("actor") or self.headers.get("X-MetaGate-Actor", "local-user")),
                )
                self._json({"review": record}, 201)
            except ToolCallDenied as error:
                self._json({
                    "error": str(error),
                    "decision_id": error.decision_id,
                    "action": error.action,
                    "contract": error.contract,
                    "enforcement": "tool_not_invoked",
                }, 403)
            except PermissionError as error:
                self._json({"error": str(error)}, 403)
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                self._json({"error": str(error)}, 400)
            except Exception as error:
                # A failed live/fixture read must fail closed. In particular,
                # never let an evaluator exception tear down the HTTP
                # connection and leave an agent guessing whether its tool ran.
                self._json({
                    "error": f"MetaGate could not evaluate this request: {error}",
                    "enforcement": "tool_not_invoked",
                    "retryable": True,
                }, 503)

        def do_POST_override(self, payload: dict) -> None:
            urn = str(payload.get("urn", "")).strip()
            if not urn:
                raise ValueError("urn is required")
            actor = str(payload.get("actor") or self.headers.get("X-MetaGate-Actor", "")).strip()
            role = str(payload.get("role") or self.headers.get("X-MetaGate-Role", "requester")).strip().lower()
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
    allow_reuse_address = True

    def handle_error(self, request, client_address) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the live MetaGate Review app.")
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
        default=os.environ.get("METAGATE_CORS_ORIGIN", "*"),
        help="Allowed browser origin for the review API. Use a specific URL in private deployments.",
    )
    parser.add_argument("--capability", default="autonomous-agent-action")
    parser.add_argument(
        "--registry-file",
        default=os.environ.get("METAGATE_AGENT_REGISTRY_FILE"),
        help="DataHub-shaped Agent Registry and Service Catalog JSON.",
    )
    parser.add_argument("--agent-id", default=os.environ.get("METAGATE_AGENT_ID"))
    parser.add_argument("--skill-id", default=os.environ.get("METAGATE_SKILL_ID"))
    parser.add_argument("--tool-id", default=os.environ.get("METAGATE_TOOL_ID"))
    parser.add_argument("--service-id", default=os.environ.get("METAGATE_SERVICE_ID"))
    parser.add_argument(
        "--require-agent-registry",
        action="store_true",
        default=os.environ.get("METAGATE_REQUIRE_AGENT_REGISTRY", "0").lower() in {"1", "true", "yes"},
        help="Fail closed unless the agent, skill, tool, and service chain is verified.",
    )
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
        "--catalog-first",
        action="store_true",
        default=os.environ.get("METAGATE_CATALOG_FIRST", "1").lower() in {"1", "true", "yes"},
        help="Use the connected DataHub catalog as the authoritative asset scope in live mode.",
    )
    parser.add_argument(
        "--max-assets",
        type=int,
        default=int(os.environ.get("METAGATE_MAX_ASSETS", "0")),
        help="Maximum discovered datasets to score; 0 means all datasets returned by DataHub.",
    )
    parser.add_argument(
        "--urn",
        action="append",
        dest="urns",
        help="DataHub URN to evaluate. Repeat for multiple assets.",
    )
    args = parser.parse_args()
    if args.max_assets < 0:
        raise ReviewConfigError("--max-assets cannot be negative.")
    if args.catalog_first and args.datahub_file:
        raise ReviewConfigError("--catalog-first requires --datahub-url, not --datahub-file.")
    if args.catalog_first:
        args.discover_assets = True

    demo_mode = os.environ.get("METAGATE_DEMO_MODE", "").strip().lower()
    if demo_mode not in {"", "fixture", "live"}:
        raise ReviewConfigError("METAGATE_DEMO_MODE must be 'fixture' or 'live'.")
    if demo_mode == "live":
        # Hosted live mode must be explicit and fail closed. In particular, a
        # missing endpoint must never turn into a convincing fixture page.
        if args.datahub_file:
            raise ReviewConfigError("METAGATE_DEMO_MODE=live cannot use --datahub-file.")
        if not (args.datahub_url or os.environ.get("DATAHUB_GRAPHQL_URL")):
            raise ReviewConfigError(
                "METAGATE_DEMO_MODE=live requires DATAHUB_GRAPHQL_URL or --datahub-url."
            )
        args.no_recorded_fallback = True

    state = ReviewState(
        args.policy,
        args.datahub_url,
        args.datahub_file,
        allow_recorded_fallback=not args.no_recorded_fallback,
        max_hops=args.max_hops,
        registry_path=args.registry_file,
        agent_id=args.agent_id,
        skill_id=args.skill_id,
        tool_id=args.tool_id,
        service_id=args.service_id,
        require_agent_registry=args.require_agent_registry,
        catalog_first=args.catalog_first,
    )
    urns = [] if args.catalog_first else (args.urns or DEFAULT_URNS)
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
    print(f"MetaGate Review is running at http://{args.host}:{args.port}/review")
    print(f"Serving app from {APP}")
    if args.discover_assets:
        print(
            "Automatic DataHub catalog scan enabled (all datasets per refresh)."
            if args.max_assets <= 0
            else f"Automatic DataHub asset discovery enabled (up to {args.max_assets} datasets per refresh)."
        )
    server.serve_forever()


if __name__ == "__main__":
    main()
