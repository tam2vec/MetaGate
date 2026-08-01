import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from context_gradient.datahub.adapter import DataHubEvidenceExtractor, DataHubWriteback, GraphQLDataHubClient
from context_gradient.datahub.mock_client import FileDataHubClient
from context_gradient.scanner import BackgroundScanner
from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.history import ReadinessHistory
from context_gradient.sdk.models import EvidenceKind
from context_gradient.sdk.policy import PolicyProfile
from context_gradient.sdk.audit import AuditLog


ROOT = Path(__file__).resolve().parents[1]
URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)"


class QualityTest(unittest.TestCase):
    def test_live_writeback_fails_closed_without_mutation_config(self):
        client = GraphQLDataHubClient("http://datahub.invalid/api/graphql")
        with self.assertRaisesRegex(RuntimeError, "Live write-back is not configured"):
            DataHubWriteback(client).publish("urn:li:dataset:test", {"gaps": []})
    def test_lexical_description_glossary_contradiction_is_detected(self):
        client = type("Client", (), {
            "get_entity": lambda _self, _urn: {"urn": URN, "description": {"text": "Net revenue"}, "glossary": {"terms": ["Gross Revenue"]}},
            "get_neighbors": lambda _self, _urn: [],
        })()
        bundle = DataHubEvidenceExtractor(client).bundle(URN)
        glossary = next(item for item in bundle.entity.evidence if item.kind == EvidenceKind.GLOSSARY)
        self.assertTrue(glossary.contradictory)

    def test_graphql_query_can_be_overridden_for_datahub_version(self):
        client = GraphQLDataHubClient("http://invalid", query="query Custom($urn: String!) { entity(urn: $urn) { urn } }")
        with patch.object(client, "_request", return_value={"entity": {"urn": URN}}) as request:
            client.get_entity(URN)
            self.assertEqual(request.call_args.args[0], client.query)

    def test_missing_incidents_are_not_treated_as_zero_open_incidents(self):
        client = type("Client", (), {
            "get_entity": lambda _self, _urn: {"urn": URN},
            "get_neighbors": lambda _self, _urn: [],
        })()
        bundle = DataHubEvidenceExtractor(client).bundle(URN)
        incidents = next(item for item in bundle.entity.evidence if item.kind == EvidenceKind.INCIDENTS)
        self.assertFalse(incidents.present)

    def test_empty_metadata_containers_are_not_treated_as_evidence(self):
        client = type("Client", (), {
            "get_entity": lambda _self, _urn: {
                "urn": URN,
                "glossary": {"terms": []},
                "lineage": {"upstreams": []},
                "tags": {"values": []},
                "freshness": {},
                "usage": {"buckets": []},
                "policy": {},
            },
            "get_neighbors": lambda _self, _urn: [],
        })()
        bundle = DataHubEvidenceExtractor(client).bundle(URN)
        for kind in (EvidenceKind.GLOSSARY, EvidenceKind.LINEAGE, EvidenceKind.TAGS, EvidenceKind.FRESHNESS, EvidenceKind.USAGE, EvidenceKind.POLICY):
            item = next(item for item in bundle.entity.evidence if item.kind == kind)
            self.assertFalse(item.present, kind.value)

    def test_writeback_returns_verified_receipt_and_scan_time(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            client = FileDataHubClient(ROOT / "examples/data/datahub_graph.json", path / "writeback.json")
            receipt = DataHubWriteback(client).publish(URN, {"gaps": []})
            self.assertTrue(receipt["certificate_written"])
            scanner = BackgroundScanner(DataHubEvidenceExtractor(client), ReadinessEngine(PolicyProfile("test", {}, {}, [])), ReadinessHistory(path / "history"), audit_log=AuditLog(path / "audit.jsonl"))
            result = scanner.handle_metadata_events([URN])[0]
            self.assertGreaterEqual(result.duration_ms, 0)
            self.assertTrue((path / "audit.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
