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
        self.assertIn("--catalog-first", dockerfile)
        self.assertIn('METAGATE_MAX_ASSETS:-0', dockerfile)
        self.assertIn("six_asset_review_graph.json", dockerfile)
        self.assertIn("METAGATE_BUILD_ID", dockerfile)

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

    def test_review_evidence_prefers_selected_action_status(self):
        page = (ROOT / "public-demo/index.html").read_text()
        self.assertIn(
            "contract && contract.evidence_status && contract.evidence_status[key]",
            page,
        )

    def test_live_launcher_discovers_without_replacing_proof_assets(self):
        launcher = (ROOT / "scripts/start_metagate_review.sh").read_text()
        autostart = (ROOT / "scripts/install_metagate_autostart.sh").read_text()
        self.assertIn('METAGATE_DISCOVER_ASSETS="${METAGATE_DISCOVER_ASSETS:-1}"', launcher)
        self.assertIn('METAGATE_CATALOG_FIRST="${METAGATE_CATALOG_FIRST:-1}"', launcher)
        self.assertIn("--discover-assets", autostart)
        self.assertIn("--catalog-first", autostart)
        self.assertIn("--max-assets", autostart)
        self.assertIn("<key>METAGATE_CATALOG_FIRST</key>", autostart)
        self.assertIn("METAGATE_FORCE_RESTART", launcher)

    def test_review_page_exposes_scope_integrity_to_the_user(self):
        page = (ROOT / "public-demo/index.html").read_text()
        self.assertIn('id="scopeProof"', page)
        self.assertIn("configured proof asset", page)
        self.assertIn("additional DataHub asset", page)
        self.assertIn("configured_assets_retained", page)
        self.assertIn("renderScopeProof(payload, status)", page)
        self.assertIn("catalog_authoritative", page)
        self.assertIn("Connected DataHub catalog", page)
        self.assertIn("&limit=0&refresh=1", page)

    def test_launchers_use_the_canonical_python_path(self):
        for name in ("start_metagate_review.sh", "start_metagate_demo.sh", "verify_metagate.sh", "judge_proof.sh"):
            script = (ROOT / "scripts" / name).read_text()
            self.assertIn("PYTHONPATH=src", script, name)

    def test_release_proof_separates_deterministic_and_external_checks(self):
        script = (ROOT / "scripts/build_release_proof.py").read_text()
        self.assertIn('"deterministic_proof"', script)
        self.assertIn('"external_proof_required"', script)
        self.assertIn('"live_schema_contract"', script)
        self.assertIn('scripts/probe_datahub_mcp.py', script)
        self.assertIn('configured_but_unverified', script)
        self.assertIn('independent reviewers', script)


if __name__ == "__main__":
    unittest.main()
