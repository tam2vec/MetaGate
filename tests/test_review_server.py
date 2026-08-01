import unittest

from scripts.serve_review import ReviewState


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
