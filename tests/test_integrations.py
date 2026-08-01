import tempfile
import unittest
from pathlib import Path

from context_gradient.datahub.adapter import DataHubEvidenceExtractor, GraphQLDataHubClient
from context_gradient.datahub.mock_client import FileDataHubClient
from context_gradient.scanner import BackgroundScanner
from context_gradient.sdk.cache import JsonCache
from context_gradient.sdk.admission import admit_capability
from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.history import ReadinessHistory
from context_gradient.sdk.policy import load_policy


ROOT = Path(__file__).resolve().parents[1]
URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)"


class FakeGraphQLClient(GraphQLDataHubClient):
    def _request(self, query, variables):
        return {"entity": {"urn": variables["urn"], "type": "dataset", "ownership": {"owners": []}, "glossaryTerms": {"terms": []}, "upstreamLineage": {"upstreams": []}, "assertions": {"assertions": []}, "incidents": {"incidents": []}, "properties": []}}


class IntegrationTest(unittest.TestCase):
    def test_cache_and_historical_diff_are_connected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            policy = load_policy(ROOT / "examples/policies/enterprise_ai.yml")
            client = FileDataHubClient(ROOT / "examples/data/datahub_graph.json")
            extractor = DataHubEvidenceExtractor(client, JsonCache(path / "cache.json"))
            scanner = BackgroundScanner(extractor, ReadinessEngine(policy), ReadinessHistory(path / "history"))
            first = scanner.handle_metadata_events([URN])[0]
            second = scanner.handle_metadata_events([URN])[0]
            self.assertIsNone(first.diff.previous_score)
            self.assertEqual(second.diff.previous_score, first.certificate["readiness_score"])
            decision = admit_capability(first.certificate, "rename-column")
            self.assertFalse(decision.allowed)
            self.assertTrue(first.certificate["metadata"]["connected_assets"] >= 1)

    def test_graphql_response_normalizes_to_sdk_shape(self):
        entity = FakeGraphQLClient().get_entity(URN)
        self.assertEqual(entity["urn"], URN)
        self.assertIn("ownership", entity)
        self.assertIn("lineage", entity)

    def test_extractor_traverses_multiple_hops(self):
        class ChainClient:
            def get_entity(self, urn):
                return {"urn": urn, "type": "dataset", "ownership": {"owners": [urn]}}

            def get_neighbors(self, urn):
                index = int(urn.rsplit(":", 1)[-1])
                return [{"urn": f"urn:test:{index + 1}", "ownership": {"owners": ["owner"]}}] if index < 3 else []

        bundle = DataHubEvidenceExtractor(ChainClient(), max_hops=3).bundle("urn:test:0")
        self.assertEqual(set(bundle.neighbors), {"urn:test:1", "urn:test:2", "urn:test:3"})


if __name__ == "__main__":
    unittest.main()
