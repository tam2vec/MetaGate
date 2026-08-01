import json
import unittest
from pathlib import Path
from unittest.mock import patch

from context_gradient.datahub.adapter import DataHubEvidenceExtractor, GraphQLDataHubClient
from context_gradient.scanner import BackgroundScanner
from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.history import ReadinessHistory
from context_gradient.sdk.models import EvidenceKind
from context_gradient.sdk.policy import CapabilityPolicy, PolicyProfile


URN = "urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.revenue,PROD)"


class SeededDataHub:
    def __init__(self):
        self.assertion_passing = False
        self.entities = {
            URN: {
                "urn": URN, "type": "dataset",
                "editableProperties": {"description": "Finance revenue"},
                "ownership": {"owners": [{"owner": {"urn": "urn:li:corpuser:finance"}}]},
                "glossaryTerms": {"terms": [{"term": {"urn": "urn:li:glossaryTerm:revenue"}}]},
                "domain": {"domain": {"urn": "urn:li:domain:finance"}},
                "tags": {"tags": [{"tag": {"urn": "urn:li:tag:production"}}]},
                "upstreamLineage": {"upstreams": []},
                "fineGrainedLineages": {"fineGrainedLineages": [{"upstreams": ["order_id"], "downstreams": ["revenue"]}]},
                "incidents": {"incidents": []}, "usageStats": {"buckets": []},
                "freshness": {"passed": True, "confidence": 1.0},
                "policy": {"profile": "finance-production", "confidence": 1.0},
                "dashboards": {"relationships": [{"entity": {"urn": "urn:li:chart:revenue"}}]},
                "charts": {"relationships": []}, "mlModels": {"relationships": []},
                "properties": [],
            }
        }

    def payload(self, urn):
        entity = dict(self.entities[urn])
        entity["assertions"] = {"assertions": [{"urn": "urn:li:assertion:freshness", "result": {"status": "SUCCESS"}}]} if self.assertion_passing else {"assertions": []}
        return {"data": {"entity": entity}}


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


class LiveSeededIntegrationTest(unittest.TestCase):
    def test_metadata_fix_unlocks_capability_through_graphql_and_diff(self):
        seed = SeededDataHub()
        def fake_urlopen(request, timeout):
            body = json.loads(request.data.decode())
            return FakeResponse(seed.payload(body["variables"]["urn"]))

        with patch("context_gradient.datahub.adapter.urlopen", side_effect=fake_urlopen):
            policy = PolicyProfile(
                "finance-production",
                {kind: 1.0 for kind in EvidenceKind},
                {},
                [CapabilityPolicy("trust-kpi", 80, 70, [EvidenceKind.ASSERTIONS, EvidenceKind.OWNERSHIP, EvidenceKind.FRESHNESS])],
            )
            client = GraphQLDataHubClient("http://seeded-datahub.invalid/api/graphql")
            with __import__("tempfile").TemporaryDirectory() as directory:
                scanner = BackgroundScanner(DataHubEvidenceExtractor(client), ReadinessEngine(policy), ReadinessHistory(Path(directory)))
                before = scanner.handle_metadata_events([URN])[0]
                self.assertNotIn("trust-kpi", before.certificate["context_contract"]["allowed_capabilities"])
                seed.assertion_passing = True
                after = scanner.handle_metadata_events([URN])[0]
                self.assertIn("trust-kpi", after.certificate["context_contract"]["allowed_capabilities"])
                self.assertIn("trust-kpi", after.diff.newly_certified)


if __name__ == "__main__":
    unittest.main()
