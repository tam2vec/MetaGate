import unittest
from pathlib import Path

from context_gradient.datahub.adapter import DataHubEvidenceExtractor, DataHubWriteback
from context_gradient.datahub.mock_client import FileDataHubClient
from context_gradient.scanner import BackgroundScanner
from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.history import ReadinessHistory
from context_gradient.sdk.policy import load_policy


ROOT = Path(__file__).resolve().parents[1]
URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)"


class EngineTest(unittest.TestCase):
    def test_end_to_end_certification_and_writeback(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            tmp_path = Path(directory)
            policy = load_policy(ROOT / "examples/policies/enterprise_ai.yml")
            client = FileDataHubClient(
                ROOT / "examples/data/datahub_graph.json",
                tmp_path / "writeback.json",
            )
            scanner = BackgroundScanner(
                DataHubEvidenceExtractor(client),
                ReadinessEngine(policy),
                ReadinessHistory(tmp_path / "history"),
                DataHubWriteback(client),
            )

            result = scanner.handle_metadata_events([URN])[0]

            self.assertEqual(result.certificate["entity_urn"], URN)
            self.assertGreaterEqual(result.certificate["readiness_score"], 80)
            self.assertIn(
                "answer-business-questions",
                result.certificate["context_contract"]["allowed_capabilities"],
            )
            self.assertTrue((tmp_path / "writeback.json").exists())
            self.assertTrue(list((tmp_path / "history").glob("*.json")))

    def test_gap_classification_for_neighbor_penalty(self):
        policy = load_policy(ROOT / "examples/policies/enterprise_ai.yml")
        client = FileDataHubClient(ROOT / "examples/data/datahub_graph.json")
        bundle = DataHubEvidenceExtractor(client).bundle(URN)
        certificate = ReadinessEngine(policy).certify(bundle)

        self.assertEqual(certificate.context_contract.entity_urn, URN)
        self.assertLess(certificate.readiness_score, 100)
        self.assertGreater(certificate.confidence, 80)


if __name__ == "__main__":
    unittest.main()
