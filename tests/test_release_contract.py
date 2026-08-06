import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReleaseContractTest(unittest.TestCase):
    def test_container_contains_the_review_page_and_runtime_port_contract(self):
        dockerfile = (ROOT / "Dockerfile").read_text()
        self.assertIn("COPY public-demo ./public-demo", dockerfile)
        self.assertIn('PORT=\\\"${PORT:-8765}\\\"', dockerfile)
        self.assertIn("--discover-assets", dockerfile)
        self.assertIn("six_asset_review_graph.json", dockerfile)
        self.assertIn("PREDICATE_BUILD_ID", dockerfile)

    def test_six_asset_proof_is_explicit_and_complete(self):
        graph = json.loads((ROOT / "examples/data/six_asset_review_graph.json").read_text())
        urns = list(graph.get("entities", {}).keys())
        expected = {
            "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)",
            "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)",
            "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_deleted,PROD)",
            "urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)",
            "urn:li:dataset:(urn:li:dataPlatform:kafka,SampleKafkaDataset,PROD)",
            "urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.customer_lifetime_value,PROD)",
        }
        self.assertTrue(expected.issubset(set(urns)))

    def test_review_page_rechecks_action_and_prevents_stale_responses(self):
        page = (ROOT / "public-demo/index.html").read_text()
        self.assertIn('capabilitySelect.addEventListener("change"', page)
        self.assertIn("loadCapabilityDecision(capabilitySelect.value)", page)
        self.assertIn("new AbortController()", page)
        self.assertIn("requestId !== evaluationSequence", page)
        self.assertIn('signal: evaluationController.signal', page)

    def test_launchers_use_the_canonical_python_path(self):
        for name in ("start_predicate_review.sh", "start_predicate_demo.sh", "verify_predicate.sh", "judge_proof.sh"):
            script = (ROOT / "scripts" / name).read_text()
            self.assertIn("PYTHONPATH=src", script, name)

    def test_release_proof_separates_deterministic_and_external_checks(self):
        script = (ROOT / "scripts/build_release_proof.py").read_text()
        self.assertIn('"deterministic_proof"', script)
        self.assertIn('"external_proof_required"', script)
        self.assertIn('"live_schema_contract"', script)


if __name__ == "__main__":
    unittest.main()
