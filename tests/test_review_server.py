import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

from metagate.review import DEFAULT_URNS, ReviewConfigError, ReviewState
from metagate.review_store import ReviewStore


class ReviewServerTest(unittest.TestCase):
    def test_fixture_snapshot_does_not_age_but_explicit_stale_evidence_does(self):
        state = ReviewState(
            "examples/policies/enterprise_ai.yml",
            datahub_url=None,
            datahub_file="examples/data/six_asset_review_graph.json",
        )

        sample = state.evaluate(
            "urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)",
            "answer-business-questions",
        )
        kafka = state.evaluate(
            "urn:li:dataset:(urn:li:dataPlatform:kafka,SampleKafkaDataset,PROD)",
            "answer-business-questions",
        )

        self.assertEqual(sample["decision"], "allowed")
        self.assertGreater(sample["readiness"], 90)
        self.assertEqual(sample["evidence_status"]["freshness"], "present")
        self.assertEqual(kafka["decision"], "blocked")
        self.assertIn("freshness", kafka["reason"])

    def test_review_server_returns_ui_run_shape(self):
        state = ReviewState(
            "examples/policies/enterprise_ai.yml",
            datahub_url=None,
            datahub_file="examples/data/datahub_graph.json",
        )

        run = state.evaluate(
            "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)",
            "autonomous-agent-action",
        )

        self.assertEqual(run["decision"], "allowed")
        self.assertEqual(run["asset"], "analytics.revenue_daily")
        self.assertEqual(run["metagate"]["action"], "autonomous-agent-action")
        self.assertEqual(run["readiness"], run["capability_score"])
        self.assertEqual(run["confidence"], run["capability_confidence"])
        self.assertNotEqual(run["readiness"], run["overall_readiness"])

    def test_review_server_rejects_missing_source_config(self):
        with self.assertRaises(ReviewConfigError):
            ReviewState(
                "examples/policies/enterprise_ai.yml",
                datahub_url=None,
                datahub_file=None,
            )

    def test_environment_endpoint_is_treated_as_live_source(self):
        with patch.dict(os.environ, {"DATAHUB_GRAPHQL_URL": "http://datahub.test/api/graphql"}):
            state = ReviewState(
                "examples/policies/enterprise_ai.yml",
                datahub_url=None,
                datahub_file=None,
            )

        self.assertEqual(state.datahub_url, "http://datahub.test/api/graphql")
        self.assertFalse(state.allow_recorded_fallback)
        self.assertTrue(state.health()["live_datahub"])

    def test_review_server_health_and_readiness(self):
        state = ReviewState(
            "examples/policies/enterprise_ai.yml",
            datahub_url=None,
            datahub_file="examples/data/datahub_graph.json",
        )

        self.assertEqual(state.health()["status"], "ok")
        self.assertEqual(state.health()["mode"], "fixture")
        readiness = state.ready(
            ["urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)"],
            "autonomous-agent-action",
        )
        self.assertEqual(readiness["status"], "ready")
        self.assertEqual(readiness["runs_returned"], 1)

    def test_review_server_status_explains_fixture_mode(self):
        state = ReviewState(
            "examples/policies/enterprise_ai.yml",
            datahub_url=None,
            datahub_file="examples/data/datahub_graph.json",
        )

        status = state.status(
            ["urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)"],
            "autonomous-agent-action",
        )

        self.assertEqual(status["product"], "MetaGate")
        self.assertEqual(status["mode"], "fixture-api")
        self.assertEqual(status["data_source"], "local fixture")
        self.assertTrue(status["ready"])

    def test_registry_status_uses_the_same_defaults_as_evaluation(self):
        state = ReviewState(
            "examples/policies/enterprise_ai.yml",
            datahub_url=None,
            datahub_file="examples/data/datahub_graph.json",
            require_agent_registry=True,
        )

        status = state.status(
            ["urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)"],
            "autonomous-agent-action",
        )

        registry = status["agent_registry"]
        self.assertEqual(registry["agent_urn"], "urn:li:aiAgent:metagate-review-agent")
        self.assertEqual(registry["skill_urn"], "urn:li:agentSkill:metagate-preflight")
        self.assertEqual(registry["tool_urn"], "urn:li:api:metagate.evaluate")
        self.assertEqual(registry["service_urn"], "urn:li:service:metagate-review-api")

    def test_six_asset_fixture_status_exposes_exact_proof_scope(self):
        state = ReviewState(
            "examples/policies/enterprise_ai.yml",
            datahub_url=None,
            datahub_file="examples/data/six_asset_review_graph.json",
        )

        status = state.status(
            state.resolve_urns([], discover_assets=False),
            "autonomous-agent-action",
        )

        self.assertEqual(status["asset_scope"], "fixture: six_asset_review_graph.json")
        self.assertEqual(status["configured_asset_count"], 6)
        self.assertEqual(status["resolved_asset_count"], 6)
        self.assertEqual(status["missing_configured_assets"], [])
        self.assertTrue(status["build_id"])

    def test_live_scope_discovers_current_dataset_urns_and_honors_limit(self):
        state = ReviewState(
            "examples/policies/enterprise_ai.yml",
            datahub_url=None,
            datahub_file="examples/data/datahub_graph.json",
        )
        discovered = [
            "urn:li:dataset:(urn:li:dataPlatform:hive,one,PROD)",
            "urn:li:dataset:(urn:li:dataPlatform:hive,two,PROD)",
            "urn:li:dataset:(urn:li:dataPlatform:hive,three,PROD)",
        ]
        state.client.list_dataset_urns = lambda: discovered

        self.assertEqual(
            state.resolve_urns(["urn:fixed"], discover_assets=True, max_assets=2),
            ["urn:fixed", *discovered[:1]],
        )
        self.assertIsNone(state.discovery_error)

    def test_live_scope_keeps_configured_proof_assets_when_catalog_is_partial(self):
        state = ReviewState(
            "examples/policies/enterprise_ai.yml",
            datahub_url=None,
            datahub_file="examples/data/datahub_graph.json",
        )
        configured = ["urn:configured-one", "urn:configured-two"]
        state.client.list_dataset_urns = lambda: ["urn:configured-one", "urn:catalog-only"]

        self.assertEqual(
            state.resolve_urns(configured, discover_assets=True, max_assets=10),
            ["urn:configured-one", "urn:configured-two", "urn:catalog-only"],
        )

    def test_discovery_empty_catalog_keeps_configured_assets_and_explains_state(self):
        state = ReviewState(
            "examples/policies/enterprise_ai.yml",
            datahub_url=None,
            datahub_file="examples/data/datahub_graph.json",
        )
        state.client.list_dataset_urns = lambda: []

        self.assertEqual(
            state.resolve_urns(["urn:configured"], discover_assets=True),
            ["urn:configured"],
        )
        self.assertIn("returned no dataset URNs", state.discovery_error)

    def test_empty_discovery_without_explicit_assets_keeps_default_proof_scope(self):
        state = ReviewState(
            "examples/policies/enterprise_ai.yml",
            datahub_url=None,
            datahub_file="examples/data/datahub_graph.json",
        )
        state.client.list_dataset_urns = lambda: []

        resolved = state.resolve_urns([], discover_assets=True)

        self.assertEqual(resolved, DEFAULT_URNS)
        self.assertEqual(len(resolved), 6)
        self.assertIn("returned no dataset URNs", state.discovery_error)

    def test_scan_empty_configuration_uses_default_proof_scope(self):
        state = ReviewState(
            "examples/policies/enterprise_ai.yml",
            datahub_url=None,
            datahub_file="examples/data/six_asset_review_graph.json",
        )
        state.client.list_dataset_urns = lambda: []

        result = state.scan([], "answer-business-questions", limit=10, refresh=False)

        self.assertEqual(result["configured_asset_count"], 6)
        self.assertEqual(result["discovered_asset_count"], 0)
        self.assertEqual(result["scope_integrity"]["configured_assets_retained"], True)
        self.assertEqual(result["scope_integrity"]["missing_configured_assets"], [])

    def test_live_scope_keeps_configured_assets_after_discovery_error(self):
        state = ReviewState(
            "examples/policies/enterprise_ai.yml",
            datahub_url="http://datahub.test/api/graphql",
            datahub_file=None,
            catalog_first=False,
        )
        state.client.list_dataset_urns = lambda: (_ for _ in ()).throw(RuntimeError("catalog unavailable"))

        self.assertEqual(state.resolve_urns(["urn:fixed"], discover_assets=True), ["urn:fixed"])
        self.assertEqual(state.discovery_error, "catalog unavailable")

    def test_live_source_defaults_to_catalog_first(self):
        state = ReviewState(
            "examples/policies/enterprise_ai.yml",
            datahub_url="http://datahub.test/api/graphql",
            datahub_file=None,
        )

        self.assertTrue(state.catalog_first)

    def test_catalog_first_uses_every_discovered_dataset_and_ignores_proof_scope(self):
        state = ReviewState(
            "examples/policies/enterprise_ai.yml",
            datahub_url="http://datahub.test/api/graphql",
            datahub_file=None,
            catalog_first=True,
        )
        discovered = [
            "urn:li:dataset:(urn:li:dataPlatform:snowflake,orders,PROD)",
            "urn:li:dataset:(urn:li:dataPlatform:postgres,customers,PROD)",
            "urn:li:dataset:(urn:li:dataPlatform:kafka,events,PROD)",
        ]
        state.client.list_dataset_urns = lambda: discovered

        self.assertEqual(
            state.resolve_urns(["urn:proof-only"], discover_assets=True, max_assets=0),
            discovered,
        )
        self.assertIsNone(state.discovery_error)

    def test_catalog_first_zero_limit_has_no_hidden_cap(self):
        state = ReviewState(
            "examples/policies/enterprise_ai.yml",
            datahub_url="http://datahub.test/api/graphql",
            datahub_file=None,
            catalog_first=True,
        )
        discovered = [f"urn:li:dataset:(urn:li:dataPlatform:hive,table_{i},PROD)" for i in range(125)]
        state.client.list_dataset_urns = lambda: discovered

        self.assertEqual(
            state.resolve_urns([], discover_assets=True, max_assets=0),
            discovered,
        )

    def test_catalog_first_empty_or_failed_catalog_does_not_fallback_to_proof_assets(self):
        state = ReviewState(
            "examples/policies/enterprise_ai.yml",
            datahub_url="http://datahub.test/api/graphql",
            datahub_file=None,
            catalog_first=True,
        )
        state.client.list_dataset_urns = lambda: []

        self.assertEqual(state.resolve_urns([], discover_assets=True), [])
        self.assertIn("returned no dataset URNs", state.discovery_error)

        state.client.list_dataset_urns = lambda: (_ for _ in ()).throw(RuntimeError("catalog unavailable"))
        self.assertEqual(state.resolve_urns([], discover_assets=True), [])
        self.assertEqual(state.discovery_error, "catalog unavailable")

    def test_catalog_first_rejects_fixture_source(self):
        with self.assertRaises(ReviewConfigError):
            ReviewState(
                "examples/policies/enterprise_ai.yml",
                datahub_url=None,
                datahub_file="examples/data/six_asset_review_graph.json",
                catalog_first=True,
            )

    def test_human_reviews_are_persisted_server_side(self):
        state = ReviewState(
            "examples/policies/enterprise_ai.yml",
            datahub_url=None,
            datahub_file="examples/data/datahub_graph.json",
        )
        record = state.save_review("urn:test", "answer-business-questions", "agree", "The evidence supports this.")
        self.assertEqual(state.reviews("urn:test", "answer-business-questions")[-1], record)

    def test_sqlite_history_survives_a_new_state_instance(self):
        with tempfile.TemporaryDirectory() as directory:
            state = ReviewState("examples/policies/enterprise_ai.yml", datahub_url=None, datahub_file="examples/data/datahub_graph.json")
            state.review_store = ReviewStore(Path(directory) / "review.sqlite3")
            state.review_store.path.parent.mkdir(parents=True, exist_ok=True)
            state.review_store._init()
            run = state.evaluate("urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)", "autonomous-agent-action")
            fresh = type(state.review_store)(state.review_store.path)
            self.assertEqual(fresh.latest_decision(run["urn"], run["capability"])["decision_id"], run["decision_id"])

    def test_checked_asset_is_visible_after_new_review_state(self):
        with tempfile.TemporaryDirectory() as directory:
            state = ReviewState(
                "examples/policies/enterprise_ai.yml",
                datahub_url=None,
                datahub_file="examples/data/datahub_graph.json",
            )
            state.review_store = ReviewStore(Path(directory) / "review.sqlite3")
            state.review_store.path.parent.mkdir(parents=True, exist_ok=True)
            state.review_store._init()
            checked_urn = "urn:li:dataset:(urn:li:dataPlatform:snowflake,raw.orders,PROD)"
            state.evaluate(checked_urn, "autonomous-agent-action")

            fresh = ReviewState(
                "examples/policies/enterprise_ai.yml",
                datahub_url=None,
                datahub_file="examples/data/datahub_graph.json",
            )
            fresh.review_store.path = state.review_store.path
            fresh.review_store._init()
            runs = fresh.runs(
                ["urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)"],
                "autonomous-agent-action",
                include_saved=True,
            )

            saved = next(item for item in runs if item["urn"] == checked_urn)
            self.assertTrue(saved["saved"])
            self.assertEqual(saved["saved_source"], "review-server-sqlite")
            self.assertTrue(saved["stale_until_rechecked"])

    def test_override_requires_steward_and_is_readable(self):
        state = ReviewState("examples/policies/enterprise_ai.yml", datahub_url=None, datahub_file="examples/data/datahub_graph.json")
        with self.assertRaises(PermissionError):
            state.save_override("urn:test", "autonomous-agent-action", "allowed", "reason", "alice", "requester")
        override = state.save_override("urn:test", "autonomous-agent-action", "allowed", "Reviewed by steward", "alice", "steward")
        self.assertEqual(state.review_store.latest_override("urn:test", "autonomous-agent-action"), override)

    def test_skill_and_metagate_mcp_paths_agree_on_one_asset(self):
        state = ReviewState(
            "examples/policies/enterprise_ai.yml",
            datahub_url=None,
            datahub_file="examples/data/six_asset_review_graph.json",
        )

        proof = state.integration_proof(
            "urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)",
            "answer-business-questions",
        )

        self.assertEqual(proof["status"], "verified")
        self.assertTrue(proof["same_asset"])
        self.assertTrue(proof["same_decision"])
        self.assertTrue(proof["evidence_agreement"])
        self.assertEqual(proof["skill"]["status"], "ok")
        self.assertEqual(proof["metagate_mcp"]["status"], "ok")
        self.assertEqual(proof["skill"]["decision"], proof["metagate_mcp"]["decision"])

    def test_official_datahub_mcp_is_explicitly_unconfigured_by_default(self):
        state = ReviewState(
            "examples/policies/enterprise_ai.yml",
            datahub_url=None,
            datahub_file="examples/data/six_asset_review_graph.json",
        )
        proof = state.integration_proof(
            "urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)",
            "answer-business-questions",
        )
        self.assertEqual(proof["official_datahub_mcp"]["status"], "not_configured")
        self.assertEqual(proof["official_mcp_evidence"], {})
        self.assertEqual(proof["official_mcp_facts"], {})

    def test_configured_official_mcp_is_attached_to_the_decision_contract(self):
        fake_mcp = {
            "status": "verified",
            "checked_urn": "urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)",
            "trace": [{"method": "tools/call:get_entities", "status": "completed"}],
            "entity_call": {
                "status": "ok",
                "facts": {"owner": "urn:li:corpuser:steward"},
                "evidence": {"ownership": "present"},
            },
            "query_call": {"status": "ok"},
        }
        with patch("metagate.review.probe_datahub_mcp", return_value=fake_mcp), patch.dict(
            os.environ,
            {"METAGATE_DATAHUB_MCP_COMMAND": "uvx mcp-server-datahub@latest --transport stdio"},
            clear=False,
        ):
            state = ReviewState(
                "examples/policies/enterprise_ai.yml",
                datahub_url=None,
                datahub_file="examples/data/six_asset_review_graph.json",
            )
            run = state.evaluate(
                "urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)",
                "answer-business-questions",
            )
            proof = state.integration_proof(
                "urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)",
                "answer-business-questions",
            )

        self.assertEqual(run["official_datahub_mcp"]["status"], "verified")
        self.assertEqual(run["mcp_gate"]["status"], "verified")
        self.assertEqual(run["constraint_contract"]["official_datahub_mcp"]["status"], "verified")
        self.assertEqual(proof["official_datahub_mcp"]["status"], "verified")
        self.assertEqual(proof["mcp_trace"], fake_mcp["trace"])

    def test_required_official_mcp_blocks_when_probe_is_not_verified(self):
        with patch(
            "metagate.review.probe_datahub_mcp",
            return_value={"status": "attention_required", "trace": []},
        ), patch.dict(
            os.environ,
            {
                "METAGATE_DATAHUB_MCP_COMMAND": "fake-mcp",
                "METAGATE_REQUIRE_OFFICIAL_MCP": "1",
            },
            clear=False,
        ):
            state = ReviewState(
                "examples/policies/enterprise_ai.yml",
                datahub_url=None,
                datahub_file="examples/data/six_asset_review_graph.json",
            )
            run = state.evaluate(
                "urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)",
                "answer-business-questions",
            )

        self.assertEqual(run["decision"], "blocked")
        self.assertFalse(run["allowed"])
        self.assertIn("official_datahub_mcp.verified", run["failed_terms"])

    def test_evidence_endpoint_shape_is_evidence_first(self):
        state = ReviewState(
            "examples/policies/enterprise_ai.yml",
            datahub_url=None,
            datahub_file="examples/data/six_asset_review_graph.json",
        )
        result = state.evidence(
            "urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)",
            "answer-business-questions",
        )
        self.assertEqual(result["product"], "MetaGate")
        self.assertTrue(result["decision_id"])
        self.assertIn("assertions", result["evidence"])
        self.assertIn("freshness", result["evidence"])
        self.assertIn("score_note", result)
        self.assertIn("constraint_contract", result)

    def test_scan_keeps_configured_scope_and_adds_discovered_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            state = ReviewState(
                "examples/policies/enterprise_ai.yml",
                datahub_url=None,
                datahub_file="examples/data/six_asset_review_graph.json",
            )
            state.review_store = ReviewStore(Path(directory) / "review.sqlite3")
            configured = ["urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)"]
            state.client.list_dataset_urns = lambda: [
                "urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)",
                "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)",
            ]
            result = state.scan(configured, "answer-business-questions", limit=10)
            self.assertEqual(result["asset_count"], 2)
            self.assertEqual(result["configured_asset_count"], 1)
            self.assertEqual(result["discovered_asset_count"], 1)
            self.assertEqual(result["current_scope_count"], 2)
            self.assertEqual(result["saved_run_count"], 0)

    def test_current_scope_and_saved_checks_are_reported_separately(self):
        with tempfile.TemporaryDirectory() as directory:
            state = ReviewState(
                "examples/policies/enterprise_ai.yml",
                datahub_url=None,
                datahub_file="examples/data/six_asset_review_graph.json",
            )
            state.review_store.path = Path(directory) / "review.sqlite3"
            state.review_store.path.parent.mkdir(parents=True, exist_ok=True)
            state.review_store._init()
            saved_urn = "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)"
            state.evaluate(saved_urn, "autonomous-agent-action")

            current = ["urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)"]
            runs = state.runs(current, "autonomous-agent-action", include_saved=False)
            saved = state.saved_runs("autonomous-agent-action", exclude_urns=current)

            self.assertEqual(len(runs), 1)
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0]["urn"], saved_urn)
            self.assertTrue(saved[0]["stale_until_rechecked"])

    def test_enforcement_demo_reports_blocked_tools_as_not_invoked(self):
        state = ReviewState(
            "examples/policies/enterprise_ai.yml",
            datahub_url=None,
            datahub_file="examples/data/six_asset_review_graph.json",
        )
        result = state.enforcement_demo(
            "urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)"
        )
        self.assertEqual(result["status"], "verified-local-enforcement-demo")
        by_action = {item["action"]: item for item in result["results"]}
        self.assertTrue(by_action["answer-business-questions"]["tool_called"])
        for action in ("generate-executive-metrics", "modify-dataset", "restricted-sql"):
            self.assertFalse(by_action[action]["tool_called"])
            self.assertTrue(by_action[action]["tool_not_invoked"])
