import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReleaseContractTest(unittest.TestCase):
    def test_repository_license_is_apache_2(self):
        license_text = (ROOT / "LICENSE").read_text()
        self.assertIn("Apache License", license_text)
        self.assertIn("Version 2.0, January 2004", license_text)
        self.assertNotIn("MIT License", license_text)

    def test_official_datahub_mcp_proof_artifact_is_verified_and_honest(self):
        proof = json.loads(
            (ROOT / "examples/outputs/official-datahub-mcp-proof.json").read_text()
        )
        self.assertEqual(proof["status"], "verified")
        self.assertEqual(proof["integration"], "DataHub official MCP server")
        self.assertEqual(proof["missing_required_tools"], [])
        self.assertTrue(proof["read_only"])
        self.assertTrue(proof["entity_call"]["entity_found"])
        self.assertEqual(proof["query_call"]["query_count"], 3)
        self.assertIn("local", proof["honesty_note"].lower())
        self.assertIn("public", proof["honesty_note"].lower())

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
        self.assertIn("&refresh=0`", page)
        self.assertIn('if (document.body.dataset.reviewTarget !== "technical-proof") return;', page)

    def test_asset_picker_closes_when_navigating_to_evidence_or_repair(self):
        page = (ROOT / "public-demo/index.html").read_text()
        self.assertIn("function closeAssetPicker()", page)
        self.assertIn("function setReviewView(targetId) {\n      closeAssetPicker();", page)
        self.assertIn("function render() {\n      // The picker is an explicit control", page)
        self.assertIn("function renderAssetControls(options = {})", page)
        self.assertIn("if (!options.preservePicker) closeAssetPicker();", page)
        self.assertIn('body[data-review-target="remediation-plan"] #assetPickerMenu', page)
        self.assertIn('body[data-review-target="evidence-section"] #assetPickerMenu', page)
        self.assertIn('event.stopPropagation();\n      closeAssetPicker();\n      setReviewView(item.dataset.target);', page)
        self.assertIn("renderAssetControls({ preservePicker: true });", page)
        self.assertIn('document.addEventListener("pointerdown", (event) => {', page)
        self.assertIn('data-target="remediation-plan"', page)
        self.assertIn('data-target="evidence-section"', page)

    def test_asset_selection_scrolls_only_the_main_results_to_top(self):
        page = (ROOT / "public-demo/index.html").read_text()
        self.assertIn("function scrollMainToTop()", page)
        self.assertIn('window.scrollTo({ top: 0, behavior: "smooth" })', page)
        self.assertGreaterEqual(page.count("scrollMainToTop();"), 2)

    def test_decision_context_fills_the_review_header_with_useful_guidance(self):
        page = (ROOT / "public-demo/index.html").read_text()
        self.assertIn('class="decision-context"', page)
        self.assertIn("Before the agent acts", page)
        self.assertIn('id="decisionContextStatus"', page)
        self.assertIn("body[data-review-view=\"embed-demo\"] .environment {\n      display: none !important;", page)

    def test_intro_lookup_controls_have_breathing_room_below_the_subtitle(self):
        page = (ROOT / "public-demo/index.html").read_text()
        self.assertIn('.topbar > div:first-child > #refreshData {\n      margin-top: 16px;', page)
        self.assertIn('.asset-lookup {\n      margin-top: 20px;', page)

    def test_sidebar_has_its_own_scroll_boundary_without_filling_main_height(self):
        page = (ROOT / "public-demo/index.html").read_text()
        self.assertIn("align-items: start;", page)
        self.assertIn("position: sticky;", page)
        self.assertIn("max-height: 100vh;", page)
        self.assertIn("overscroll-behavior: contain;", page)

    def test_small_screen_header_stacks_without_desktop_widths(self):
        page = (ROOT / "public-demo/index.html").read_text()
        self.assertIn(".topbar { display: block; }", page)
        self.assertIn(".decision-context, .environment { width: 100%; margin-top: 12px; }", page)
        self.assertIn(".asset-lookup { max-width: none; }", page)
        self.assertIn(".controls, .bars, .datahub-body { grid-template-columns: 1fr; }", page)

    def test_sidebar_separates_hackathon_assets_from_the_connected_catalog(self):
        page = (ROOT / "public-demo/index.html").read_text()
        self.assertIn('const HACKATHON_DATAHUB_PROFILES = [', page)
        self.assertIn('label: "NYC Taxi"', page)
        self.assertIn('function splitAssetGroups(groups)', page)
        self.assertIn('label: "Hackathon DataHub assets"', page)
        self.assertIn('label: "Other connected DataHub assets"', page)
        self.assertIn('No official hackathon scenario is loaded in this connected DataHub yet.', page)
        self.assertIn('function assetMatchesQuery(run, group, query)', page)

    def test_live_presentation_excludes_unstable_revenue_control_but_keeps_fixture(self):
        page = (ROOT / "public-demo/index.html").read_text()
        self.assertIn("let liveCatalogMode = false;", page)
        self.assertIn(
            '"urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)"',
            page,
        )
        self.assertIn("function isPresentationExcluded(run)", page)
        self.assertIn("if (isPresentationExcluded(run)) return;", page)
        self.assertIn("Revenue Daily", page)

    def test_sidebar_asset_groups_preserve_manual_open_state(self):
        page = (ROOT / "public-demo/index.html").read_text()
        self.assertIn("const sidebarGroupOpenState = new Map();", page)
        self.assertIn("const rememberedOpen = sidebarGroupOpenState.get(groupPanel.dataset.groupKey);", page)
        self.assertIn("sidebarGroupOpenState.set(groupPanel.dataset.groupKey, groupPanel.open);", page)

    def test_visible_asset_headings_use_the_catalog_name_without_internal_prefix(self):
        page = (ROOT / "public-demo/index.html").read_text()
        self.assertIn("function displayAssetLabel(run)", page)
        self.assertIn("return shortAssetLabel(run, group) || friendlyAssetLabel(run) || \"Asset\";", page)
        self.assertIn('document.getElementById("assetName").textContent = displayAssetLabel(run);', page)
        self.assertIn('document.getElementById("embeddedAssetName").textContent = displayAssetLabel(run);', page)
        self.assertIn('document.getElementById("drawerTitle").textContent = displayAssetLabel(run);', page)

    def test_opaque_catalog_ids_get_friendly_display_labels_without_changing_urns(self):
        page = (ROOT / "public-demo/index.html").read_text()
        self.assertIn("function isOpaqueIdentifier(value)", page)
        self.assertIn("function platformDisplayName(run)", page)
        self.assertIn('friendlyOpaqueCollectionLabel(run, root)', page)
        self.assertIn('friendlyOpaqueAssetLabel(run, leaf)', page)
        self.assertIn('title="${escapeHtml(run.asset || run.urn)}"', page)

    def test_optional_mcp_facts_do_not_render_as_an_empty_box(self):
        page = (ROOT / "public-demo/index.html").read_text()
        self.assertIn(".integration-mcp-facts:empty { display: none; }", page)
        self.assertIn("externalFacts.hidden = !externalFacts.textContent.trim();", page)

    def test_capability_matrix_uses_returned_capability_records(self):
        page = (ROOT / "public-demo/index.html").read_text()
        self.assertIn("const records = new Map((Array.isArray(run.certified_capabilities)", page)
        self.assertIn('"This capability was not returned by the current evaluation."', page)
        self.assertNotIn('run.decision === "allowed" ? "allowed" : "allowed"', page)

    def test_demo_positive_case_is_explicitly_fixture_backed(self):
        script = (ROOT / "docs/demo-script.md").read_text()
        self.assertIn("bundled DataHub-shaped fixture", script)
        self.assertIn("positive control", script)
        self.assertNotIn("select `SampleHiveDataset` with the same requested capability", script)

    def test_evaluate_endpoint_supports_explicit_refresh_control(self):
        review = (ROOT / "src/metagate/review.py").read_text()
        self.assertIn('refresh_value = query.get("refresh", ["true"])[0].lower()', review)
        self.assertIn("state.evaluate(urn, requested_capability, refresh=refresh)", review)

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

    def test_review_page_keeps_repair_steps_evidence_first(self):
        page = (ROOT / "public-demo/index.html").read_text()
        self.assertIn("function blockingEvidenceTerms(run)", page)
        self.assertIn("Scores and guardrails", page)
        self.assertIn("const assetValue =", page)
        self.assertIn("DataHub returned an incomplete fact.", page)
        self.assertIn("MetaGate does not mutate DataHub from this page", page)
        self.assertIn('id="repairPlanNote"', page)

    def test_repair_plan_explains_why_each_change_is_needed(self):
        page = (ROOT / "public-demo/index.html").read_text()
        self.assertIn(".repair-why", page)
        self.assertIn('<strong>Why:</strong>', page)
        self.assertIn("escapeHtml(repair.why)", page)

    def test_chrome_panel_keeps_evidence_compact_and_links_to_full_review(self):
        panel = (ROOT / "examples/browser-extension/metagate-datahub-panel.js").read_text()
        self.assertIn('class="metagate-section-label">Repair plan</h3>', panel)
        self.assertIn('class="metagate-section-label metagate-evidence-heading">Evidence</h3>', panel)
        self.assertIn('repairs.slice(0, 2)', panel)
        self.assertIn('Open full evidence &amp; repair plan', panel)
        self.assertIn('/review?urn=${encodeURIComponent(run.urn || run.entity_urn || "")}', panel)
        self.assertIn('8766 is the bundled positive-control fixture', panel)
        self.assertNotIn('>Repair queue</h3>', panel)
        extension_readme = (ROOT / "examples/browser-extension/README.md").read_text()
        self.assertIn("compact repair plan", extension_readme)
        self.assertIn("Evidence heading", extension_readme)

    def test_chrome_panel_recovers_from_invalidated_extension_context(self):
        panel = (ROOT / "examples/browser-extension/metagate-datahub-panel.js").read_text()
        self.assertIn("extension context invalidated", panel)
        self.assertIn("Refresh DataHub page", panel)
        self.assertIn("window.location.reload()", panel)

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
