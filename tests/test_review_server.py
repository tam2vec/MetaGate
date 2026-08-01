import unittest

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
