import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

from scripts.serve_review import ReviewConfigError, ReviewState


class ReviewServerTest(unittest.TestCase):
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
        self.assertEqual(run["predicate"]["action"], "autonomous-agent-action")
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

        self.assertEqual(status["product"], "Predicate")
        self.assertEqual(status["mode"], "fixture-api")
        self.assertEqual(status["data_source"], "local fixture")
        self.assertTrue(status["ready"])

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

        self.assertEqual(status["asset_scope"], "six-asset proof fixture")
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

    def test_live_scope_does_not_fall_back_to_fixed_assets_after_discovery_error(self):
        state = ReviewState(
            "examples/policies/enterprise_ai.yml",
            datahub_url="http://datahub.test/api/graphql",
            datahub_file=None,
        )
        state.client.list_dataset_urns = lambda: (_ for _ in ()).throw(RuntimeError("catalog unavailable"))

        self.assertEqual(state.resolve_urns(["urn:fixed"], discover_assets=True), [])
        self.assertEqual(state.discovery_error, "catalog unavailable")

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
            state.review_store.path = Path(directory) / "review.sqlite3"
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
            state.review_store.path = Path(directory) / "review.sqlite3"
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

    def test_skill_and_predicate_mcp_paths_agree_on_one_asset(self):
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
        self.assertEqual(proof["predicate_mcp"]["status"], "ok")
        self.assertEqual(proof["skill"]["decision"], proof["predicate_mcp"]["decision"])

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
