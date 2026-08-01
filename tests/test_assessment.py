import unittest

from context_gradient.datahub.adapter import DataHubEvidenceExtractor
from context_gradient.datahub.mock_client import FileDataHubClient
from context_gradient.sdk.assessment import assessment
from context_gradient.sdk.models import EntityNode, EvidenceBundle, EvidenceItem, EvidenceKind


class AssessmentTest(unittest.TestCase):
    def test_finance_profile_exposes_facts_and_rubric(self):
        urn = "urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.customer_lifetime_value,PROD)"
        bundle = DataHubEvidenceExtractor(FileDataHubClient("examples/data/difficult_datahub_graph.json")).bundle(urn)
        result = assessment(bundle)

        self.assertEqual(result["profile"], "finance_table")
        self.assertIn("assertions", result["rubric"])
        self.assertEqual(result["facts"]["assertions"]["passing"], 1)
        self.assertEqual(result["facts"]["assertions"]["failing"], 2)
        self.assertEqual(result["facts"]["assertions"]["count"], 3)
        self.assertEqual(result["facts"]["freshness"]["minutes_late"], 2880)
        self.assertTrue(any(check["status"] == "needs attention" for check in result["checks"]))

    def test_kafka_profile_has_stream_specific_checks(self):
        urn = "urn:li:dataset:(urn:li:dataPlatform:kafka,SampleKafkaDataset,PROD)"
        evidence = [EvidenceItem(kind, True) for kind in (EvidenceKind.OWNERSHIP, EvidenceKind.LINEAGE, EvidenceKind.ASSERTIONS, EvidenceKind.FRESHNESS, EvidenceKind.INCIDENTS)]
        bundle = EvidenceBundle(EntityNode(urn=urn, evidence=evidence))
        result = assessment(bundle)

        self.assertEqual(result["profile"], "kafka_stream")
        self.assertTrue(any("consumer lag" in check["check"] for check in result["checks"]))


if __name__ == "__main__":
    unittest.main()
