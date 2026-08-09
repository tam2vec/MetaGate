import json
import tempfile
import unittest
from pathlib import Path

from context_gradient.datahub.adapter import DataHubEvidenceExtractor, DataHubWriteback
from context_gradient.datahub.mock_client import FileDataHubClient
from context_gradient.scanner import BackgroundScanner
from context_gradient.sdk.cache import JsonCache
from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.history import ReadinessHistory
from context_gradient.sdk.policy import load_policy


ROOT = Path(__file__).resolve().parents[1]
URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)"


class RegressionTest(unittest.TestCase):
    def test_live_capability_checks_can_reuse_a_short_lived_bundle(self):
        class CountingClient:
            def __init__(self):
                self.entity_reads = 0
                self.neighbor_reads = 0

            def get_entity(self, urn):
                self.entity_reads += 1
                return {"urn": urn, "owner": ["urn:li:corpuser:analytics"]}

            def get_neighbors(self, urn):
                self.neighbor_reads += 1
                return []

        client = CountingClient()
        extractor = DataHubEvidenceExtractor(client)
        extractor.bundle(URN)
        extractor.bundle(URN)

        self.assertEqual(client.entity_reads, 1)
        self.assertEqual(client.neighbor_reads, 1)

        extractor.invalidate(URN)
        extractor.bundle(URN)
        self.assertEqual(client.entity_reads, 2)

    def test_metadata_event_does_not_reuse_stale_evidence_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            source = json.loads((ROOT / "examples/data/datahub_graph.json").read_text())
            fixture = directory / "graph.json"
            fixture.write_text(json.dumps(source))
            client = FileDataHubClient(fixture)
            extractor = DataHubEvidenceExtractor(client, JsonCache(directory / "cache.json"))
            scanner = BackgroundScanner(extractor, ReadinessEngine(load_policy(ROOT / "examples/policies/enterprise_ai.yml")), ReadinessHistory(directory / "history"))
            first = scanner.handle_metadata_events([URN])[0]
            source["entities"][URN]["freshness"] = {"minutes_late": 200, "stale": True}
            fixture.write_text(json.dumps(source))
            second = scanner.handle_metadata_events([URN])[0]
            self.assertNotEqual(first.certificate["readiness_score"], second.certificate["readiness_score"])

    def test_downstream_lineage_is_traversed(self):
        class Client:
            def get_entity(self, urn):
                return {"urn": urn, "upstreams": [], "downstreams": ["urn:downstream"]}

            def get_neighbors(self, urn):
                return [{"urn": "urn:downstream", "upstreams": [urn], "downstreams": []}] if urn == URN else []

        bundle = DataHubEvidenceExtractor(Client()).bundle(URN)
        self.assertIn("urn:downstream", bundle.neighbors)

    def test_repeated_writeback_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            client = FileDataHubClient(ROOT / "examples/data/datahub_graph.json", directory / "writeback.json")
            certificate = {"gaps": [{"evidence_kind": "freshness", "type": "stale", "recommendation": "Refresh it."}]}
            writeback = DataHubWriteback(client)
            writeback.publish(URN, certificate)
            writeback.publish(URN, certificate)
            payload = json.loads((directory / "writeback.json").read_text())
            self.assertEqual(len(payload["tasks"]), 1)


if __name__ == "__main__":
    unittest.main()
