import unittest
from datetime import datetime, timedelta, timezone

from context_gradient.datahub.adapter import DataHubEvidenceExtractor
from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.models import EntityNode, EvidenceBundle, EvidenceItem, EvidenceKind
from context_gradient.sdk.policy import PolicyProfile


class AccuracyTest(unittest.TestCase):
    def test_zero_valued_metadata_is_present(self):
        extractor = DataHubEvidenceExtractor(type("Client", (), {})())
        item = extractor._evidence(EvidenceKind.INCIDENTS, {"open": 0, "confidence": 0.9})
        self.assertTrue(item.present)

    def test_freshness_uses_hours_not_calendar_days(self):
        now = datetime.now(timezone.utc)
        item = EvidenceItem(EvidenceKind.FRESHNESS, True, observed_at=now - timedelta(hours=25))
        bundle = EvidenceBundle(EntityNode("urn:test", evidence=[item]))
        policy = PolicyProfile("test", {EvidenceKind.FRESHNESS: 1.0}, {EvidenceKind.FRESHNESS: 1}, [])
        normalized = ReadinessEngine(policy)._normalize_staleness(bundle.items())[0]
        self.assertTrue(normalized.stale)

    def test_gap_blocks_only_capabilities_that_need_that_evidence(self):
        policy = PolicyProfile(
            "test",
            {EvidenceKind.OWNERSHIP: 1.0, EvidenceKind.FRESHNESS: 1.0},
            {},
            [],
        )
        bundle = EvidenceBundle(EntityNode("urn:test", evidence=[
            EvidenceItem(EvidenceKind.OWNERSHIP, False),
            EvidenceItem(EvidenceKind.FRESHNESS, True),
        ]))
        certificate = ReadinessEngine(policy).certify(bundle)
        self.assertTrue(certificate.gaps)

    def test_assertion_counts_without_latest_results_are_incomplete(self):
        extractor = DataHubEvidenceExtractor(type("Client", (), {})())
        item = extractor._evidence(
            EvidenceKind.ASSERTIONS,
            {"passing": 6, "failing": 0},
        )
        self.assertTrue(item.present)
        self.assertFalse(item.complete)

    def test_evidence_explanations_match_fixture_shapes(self):
        extractor = DataHubEvidenceExtractor(type("Client", (), {})())
        engine = ReadinessEngine(PolicyProfile("test", {}, {}, []))

        assertion = extractor._evidence(
            EvidenceKind.ASSERTIONS,
            {"passing": 6, "failing": 0, "latest_results": [{"status": "SUCCESS"}] * 6},
        )
        column_lineage = extractor._evidence(
            EvidenceKind.COLUMN_LINEAGE,
            {"mapped_columns": 12, "complete": True},
        )
        usage = extractor._evidence(
            EvidenceKind.USAGE,
            {"weekly_users": 44},
        )

        self.assertIn("6 assertion(s)", engine._evidence_explanation(assertion, "present"))
        self.assertIn("12 mapped column(s)", engine._evidence_explanation(column_lineage, "present"))
        self.assertIn("44 weekly user(s)", engine._evidence_explanation(usage, "present"))
