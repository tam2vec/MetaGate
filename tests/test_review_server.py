import unittest
import tempfile
from pathlib import Path

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

    def test_override_requires_steward_and_is_readable(self):
        state = ReviewState("examples/policies/enterprise_ai.yml", datahub_url=None, datahub_file="examples/data/datahub_graph.json")
        with self.assertRaises(PermissionError):
            state.save_override("urn:test", "autonomous-agent-action", "allowed", "reason", "alice", "requester")
        override = state.save_override("urn:test", "autonomous-agent-action", "allowed", "Reviewed by steward", "alice", "steward")
        self.assertEqual(state.review_store.latest_override("urn:test", "autonomous-agent-action"), override)
