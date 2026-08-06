import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from context_gradient.datahub.adapter import (
    DataHubEvidenceExtractor,
    DataHubRestWritebackClient,
    DataHubWriteback,
    GraphQLDataHubClient,
)
from context_gradient.datahub.mock_client import FileDataHubClient
from context_gradient.scanner import BackgroundScanner
from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.history import ReadinessHistory
from context_gradient.sdk.models import EvidenceBundle, EvidenceItem, EvidenceKind, EntityNode
from context_gradient.sdk.policy import CapabilityPolicy, PolicyProfile
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

    def test_default_graphql_query_uses_dataset_fragment(self):
        client = GraphQLDataHubClient("http://invalid")
        self.assertIn("dataset(urn: $urn)", client.query)
        self.assertIn("... on CorpUser { urn }", client.query)
        self.assertIn("properties { description }", client.query)
        self.assertIn("runEvents(limit: 100)", client.query)
        self.assertIn("incidents(state: ACTIVE", client.query)
        self.assertNotIn("customProperties", client.query)
        self.assertNotIn("entity(urn: $urn) { urn type editableProperties", client.query)

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

    def test_live_evidence_quality_uses_observed_richness(self):
        extractor = DataHubEvidenceExtractor(type("Client", (), {})())
        one_owner = extractor._evidence(EvidenceKind.OWNERSHIP, {"owners": ["urn:li:corpuser:one"]})
        two_owners = extractor._evidence(EvidenceKind.OWNERSHIP, {"owners": ["urn:li:corpuser:one", "urn:li:corpuser:two"]})
        self.assertTrue(one_owner.present)
        self.assertLess(one_owner.confidence, two_owners.confidence)
        self.assertIn("quality_factor", one_owner.details)

    def test_readiness_distinguishes_thin_and_rich_present_evidence(self):
        policy = PolicyProfile("test", {EvidenceKind.OWNERSHIP: 1.0}, {}, [])
        thin = EvidenceBundle(EntityNode("urn:thin", evidence=[EvidenceItem(EvidenceKind.OWNERSHIP, True, confidence=0.6, details={"quality_factor": 0.6})]))
        rich = EvidenceBundle(EntityNode("urn:rich", evidence=[EvidenceItem(EvidenceKind.OWNERSHIP, True, confidence=1.0, details={"quality_factor": 1.0})]))
        self.assertLess(ReadinessEngine(policy).certify(thin).readiness_score, ReadinessEngine(policy).certify(rich).readiness_score)

    def test_downstream_only_lineage_counts_as_lineage(self):
        extractor = DataHubEvidenceExtractor(None)
        entity = extractor._node(GraphQLDataHubClient("http://invalid")._normalize({
            "urn": "urn:li:dataset:test",
            "upstreamLineage": {"upstreams": []},
            "downstreamLineage": {"downstreams": [{"entity": {"urn": "urn:li:dataset:downstream"}}]},
            "assertions": {"assertions": []},
            "incidents": {"incidents": []},
        }, "urn:li:dataset:test"))
        lineage = next(item for item in entity.evidence if item.kind == EvidenceKind.LINEAGE)
        self.assertTrue(lineage.present)

    def test_graphql_neighbors_use_normalized_lineage(self):
        neighbor = "urn:li:dataset:(urn:li:dataPlatform:hive,downstream,PROD)"

        class Client(GraphQLDataHubClient):
            def _request(self, query, variables):
                if "ContextGradientCore" in query:
                    return {"dataset": {"urn": variables["urn"], "properties": {"description": "sample"}}}
                if "ContextGradientLineage" in query:
                    return {"scrollAcrossLineage": {"searchResults": [{"entity": {"urn": neighbor, "type": "dataset"}}]}}
                return {"dataset": {}}

        entity = Client("http://datahub.invalid").get_entity(URN)
        self.assertEqual(entity["lineage"]["downstreams"], [neighbor])
        neighbors = list(Client("http://datahub.invalid").get_neighbors(URN))
        self.assertEqual([item["urn"] for item in neighbors], [neighbor])

    def test_assertion_urn_without_latest_result_is_incomplete(self):
        extractor = DataHubEvidenceExtractor(None)
        entity = extractor._node(GraphQLDataHubClient("http://invalid")._normalize({
            "urn": "urn:li:dataset:test",
            "assertions": {"assertions": [{"urn": "urn:li:assertion:test"}]},
            "incidents": {"incidents": []},
        }, "urn:li:dataset:test"))
        assertions = next(item for item in entity.evidence if item.kind == EvidenceKind.ASSERTIONS)
        self.assertTrue(assertions.present)
        self.assertFalse(assertions.complete)

    def test_unavailable_optional_evidence_has_a_reason(self):
        normalized = GraphQLDataHubClient("http://invalid")._normalize(
            {"urn": "urn:li:dataset:test", "properties": {"description": "A table"}},
            "urn:li:dataset:test",
        )
        entity = DataHubEvidenceExtractor(None)._node(normalized)
        column_lineage = next(item for item in entity.evidence if item.kind == EvidenceKind.COLUMN_LINEAGE)
        self.assertFalse(column_lineage.available)
        self.assertIn("not returned", column_lineage.details["availability_reason"])

    def test_latest_failed_assertion_gets_no_readiness_credit(self):
        normalized = GraphQLDataHubClient("http://invalid")._normalize(
            {
                "urn": "urn:li:dataset:test",
                "assertions": {"assertions": [{
                    "urn": "urn:li:assertion:row-count",
                    "info": {"type": "ROW_COUNT"},
                    "runEvents": {"runEvents": [
                        {"timestampMillis": 1000, "status": "SUCCESS"},
                        {"timestampMillis": 2000, "status": "FAILURE"},
                    ]},
                }]},
            },
            "urn:li:dataset:test",
        )
        bundle = EvidenceBundle(DataHubEvidenceExtractor(None)._node(normalized))
        policy = PolicyProfile("assertions", {EvidenceKind.ASSERTIONS: 1.0}, {}, [])
        certificate = ReadinessEngine(policy).certify(bundle)
        self.assertLess(certificate.readiness_score, 10.0)
        self.assertTrue(any(gap.type.value == "contradictory" for gap in certificate.gaps))

    def test_duplicate_assertion_urns_count_once_using_latest_result(self):
        normalized = GraphQLDataHubClient("http://invalid")._normalize(
            {
                "urn": "urn:li:dataset:test",
                "assertions": {"assertions": [
                    {
                        "urn": "urn:li:assertion:row-count",
                        "runEvents": {"runEvents": [{"timestampMillis": 1000, "status": "SUCCESS"}]},
                    },
                    {
                        "urn": "urn:li:assertion:row-count",
                        "runEvents": {"runEvents": [{"timestampMillis": 2000, "status": "FAILURE"}]},
                    },
                ]},
            },
            "urn:li:dataset:test",
        )

        assertions = normalized["assertions"]
        self.assertEqual(assertions["count"], 1)
        self.assertEqual(assertions["passing"], 0)
        self.assertEqual(assertions["failing"], 1)

    def test_unavailable_required_evidence_counts_against_readiness(self):
        normalized = GraphQLDataHubClient("http://invalid")._normalize(
            {"urn": "urn:li:dataset:test", "properties": {"description": "sample"}},
            "urn:li:dataset:test",
        )
        bundle = EvidenceBundle(DataHubEvidenceExtractor(None)._node(normalized))
        policy = PolicyProfile("lineage", {EvidenceKind.COLUMN_LINEAGE: 1.0}, {}, [])
        certificate = ReadinessEngine(policy).certify(bundle)
        self.assertLess(certificate.readiness_score, 20.0)
        self.assertTrue(any(gap.type.value == "unavailable" for gap in certificate.gaps))

    def test_unavailable_required_evidence_blocks_action_capability(self):
        normalized = GraphQLDataHubClient("http://invalid")._normalize(
            {
                "urn": "urn:li:dataset:test",
                "ownership": {"owners": [{"owner": {"urn": "urn:li:corpuser:owner"}}]},
                "glossaryTerms": {"terms": [{"term": {"urn": "urn:li:glossaryTerm:test"}}]},
                "assertions": {"assertions": [{
                    "urn": "urn:li:assertion:test",
                    "runEvents": {"runEvents": [{"timestampMillis": 2000, "status": "COMPLETE"}]},
                }]},
                "incidents": {"incidents": []},
                "lineage": {"upstreams": [], "downstreams": []},
            },
            "urn:li:dataset:test",
        )
        bundle = EvidenceBundle(DataHubEvidenceExtractor(None)._node(normalized))
        policy = PolicyProfile(
            "strict",
            {EvidenceKind.OWNERSHIP: 1.0, EvidenceKind.GLOSSARY: 1.0, EvidenceKind.ASSERTIONS: 1.0},
            {},
            [CapabilityPolicy(
                "autonomous-agent-action",
                92.0,
                88.0,
                [EvidenceKind.OWNERSHIP, EvidenceKind.GLOSSARY, EvidenceKind.ASSERTIONS],
            )],
        )
        certificate = ReadinessEngine(policy).certify(bundle)
        action = next(cap for cap in certificate.certified_capabilities if cap.capability == "autonomous-agent-action")
        self.assertFalse(action.certified)
        self.assertTrue(action.reasons)
        self.assertLess(action.confidence, 88.0)

    def test_column_lineage_reports_unmapped_schema_fields(self):
        normalized = GraphQLDataHubClient("http://invalid")._normalize(
            {
                "urn": "urn:li:dataset:test",
                "schemaMetadata": {"fields": [{"fieldPath": "customer_id"}, {"fieldPath": "clv"}]},
                "fineGrainedLineages": {"fineGrainedLineages": [{
                    "upstreams": ["customer_id"], "downstreams": ["customer_id"]
                }]},
            },
            "urn:li:dataset:test",
        )
        column_lineage = normalized["column_lineage"]
        self.assertEqual(column_lineage["mapped_columns"], 1)
        self.assertEqual(column_lineage["missing_columns"], ["clv"])
        self.assertFalse(column_lineage["complete"])

    def test_incident_and_usage_evidence_have_observation_timestamps(self):
        normalized = GraphQLDataHubClient("http://invalid")._normalize(
            {
                "urn": "urn:li:dataset:test",
                "incidents": {"incidents": []},
                "usageStats": {"buckets": []},
            },
            "urn:li:dataset:test",
        )
        self.assertTrue(normalized["incidents"].get("observed_at"))
        self.assertTrue(normalized["usage"].get("observed_at"))

    def test_empty_live_usage_buckets_are_not_usage_evidence(self):
        normalized = GraphQLDataHubClient("http://invalid")._normalize(
            {"urn": "urn:li:dataset:test", "usageStats": {"buckets": []}},
            "urn:li:dataset:test",
        )
        usage = next(
            item for item in DataHubEvidenceExtractor(None)._node(normalized).evidence
            if item.kind == EvidenceKind.USAGE
        )
        self.assertTrue(usage.available)
        self.assertFalse(usage.present)
        self.assertNotIn("usage", normalized["_unavailable_evidence"])

    def test_live_usage_buckets_are_evidence(self):
        normalized = GraphQLDataHubClient("http://invalid")._normalize(
            {
                "urn": "urn:li:dataset:test",
                "usageStats": {"buckets": [{"duration": {"count": 3}}]},
            },
            "urn:li:dataset:test",
        )
        usage = next(
            item for item in DataHubEvidenceExtractor(None)._node(normalized).evidence
            if item.kind == EvidenceKind.USAGE
        )
        self.assertTrue(usage.present)

    def test_writeback_returns_verified_receipt_and_scan_time(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            client = FileDataHubClient(ROOT / "examples/data/datahub_graph.json", path / "writeback.json")
            receipt = DataHubWriteback(client).publish(URN, {"gaps": []})
            self.assertTrue(receipt["certificate_written"])
            self.assertTrue(receipt["written_at"])
            self.assertTrue(receipt["read_back_at"])
            self.assertTrue(receipt["verified_readback"])
            scanner = BackgroundScanner(DataHubEvidenceExtractor(client), ReadinessEngine(PolicyProfile("test", {}, {}, [])), ReadinessHistory(path / "history"), audit_log=AuditLog(path / "audit.jsonl"))
            result = scanner.handle_metadata_events([URN])[0]
            self.assertGreaterEqual(result.duration_ms, 0)
            self.assertTrue((path / "audit.jsonl").exists())

    def test_rest_writeback_preserves_properties_and_verifies_exact_contract(self):
        from datahub.metadata.schema_classes import DatasetPropertiesClass

        class FakeGraph:
            def __init__(self):
                self.aspect = DatasetPropertiesClass(
                    customProperties={"existing.key": "keep-me"},
                    description="Existing description",
                )

            def get_aspect(self, _urn, _aspect_type):
                return self.aspect

            def emit(self, proposal):
                self.aspect = proposal.aspect

        graph = FakeGraph()
        client = DataHubRestWritebackClient("http://datahub.invalid", graph=graph)
        certificate = {
            "entity_urn": URN,
            "decision": "blocked",
            "decision_id": "pred-test",
            "gaps": [],
        }

        receipt = DataHubWriteback(client).publish(URN, certificate)

        self.assertTrue(receipt["verified_readback"])
        self.assertEqual(receipt["transport"], "datahub-rest-sdk")
        self.assertEqual(receipt["property_name"], "predicate.ai_context_contract")
        self.assertEqual(graph.aspect.customProperties["existing.key"], "keep-me")
        self.assertIn("predicate.ai_context_contract", graph.aspect.customProperties)

    def test_writeback_does_not_create_tasks_before_readback(self):
        class DelayedReadback:
            def __init__(self):
                self.tasks = []
                self.reads = 0
            def write_certificate(self, urn, certificate):
                return None
            def create_remediation_task(self, urn, title, body):
                self.tasks.append(title)
            def get_written_certificate(self, urn):
                self.reads += 1
                if self.reads == 1:
                    self.assert_no_tasks()
                    return None
                return {"urn": urn, "decision": "blocked"}
            def assert_no_tasks(self):
                if self.tasks:
                    raise AssertionError("remediation task created before read-back")

        client = DelayedReadback()
        with patch.dict("os.environ", {"PREDICATE_WRITEBACK_READBACK_INTERVAL": "0"}):
            receipt = DataHubWriteback(client).publish(
                URN,
                {"decision": "blocked", "gaps": [{"evidence_kind": "freshness", "type": "missing", "recommendation": "Add a freshness SLA."}]},
            )
        self.assertTrue(receipt["verified_readback"])
        self.assertEqual(len(client.tasks), 1)

    def test_writeback_rejects_readback_for_the_wrong_asset(self):
        class WrongReadback:
            def write_certificate(self, urn, certificate):
                return None
            def create_remediation_task(self, urn, title, body):
                return None
            def get_written_certificate(self, urn):
                return {"urn": "urn:other"}

        with self.assertRaisesRegex(RuntimeError, "expected"):
            DataHubWriteback(WrongReadback()).publish(URN, {"gaps": []})

    def test_score_trace_has_human_explanation(self):
        entity = DataHubEvidenceExtractor(None)._node({
            "urn": "urn:li:dataset:test",
            "_available_evidence": ["assertions"],
            "assertions": {"count": 1, "present": True, "passing": 0, "failing": 1, "unknown": 0, "missing_results": []},
        })
        certificate = ReadinessEngine(PolicyProfile("test", {EvidenceKind.ASSERTIONS: 1.0}, {}, [])).certify(EvidenceBundle(entity)).as_dict()
        assertion_row = next(row for row in certificate["metadata"]["score_trace"]["evidence"] if row["evidence_kind"] == "assertions")
        self.assertIn("failed", assertion_row["explanation"])


if __name__ == "__main__":
    unittest.main()
