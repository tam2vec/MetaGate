import unittest

from metagate.hackathon_resources import annotate_scenario_resources, resource_catalog
from metagate.review import ReviewState


class HackathonResourcesTest(unittest.TestCase):
    def test_catalog_contains_all_named_scenarios(self):
        catalog = {item["id"]: item for item in resource_catalog()}
        expected = {
            "datahub-docs", "datahub-quickstart", "datahub-mcp-server", "agent-context-kit",
            "datahub-skills", "analytics-agent", "datahub-core", "datahub-skills-repository",
            "showcase-ecommerce", "bootstrap", "nyc-taxi", "healthcare",
            "fiction-retail", "datahub-slack", "datahub-town-halls",
        }
        self.assertEqual(expected, set(catalog))
        self.assertEqual("https://github.com/acryldata/mcp-server-datahub", catalog["datahub-mcp-server"]["url"])
        self.assertEqual("https://docs.datahub.com/docs/dev-guides/agent-context/agent-context", catalog["agent-context-kit"]["url"])
        self.assertEqual("datahub datapack load showcase-ecommerce --force", catalog["showcase-ecommerce"]["load_command"])
        self.assertIn("static-assets/tree/main/datasets/nyc-taxi", catalog["nyc-taxi"]["url"])
        self.assertEqual("raw -> staging -> mart (linear)", catalog["nyc-taxi"]["pipeline_shape"])
        self.assertEqual(["healthcare.db"], catalog["healthcare"]["database_files"])
        self.assertEqual("10 flat tables (no views)", catalog["fiction-retail"]["pipeline_shape"])

    def test_scenarios_are_loaded_only_when_matching_urns_exist(self):
        resources = annotate_scenario_resources(resource_catalog(), [
            "urn:li:dataset:(urn:li:dataPlatform:postgres,nyc_taxi_mart,PROD)",
            "urn:li:dataset:(urn:li:dataPlatform:postgres,unrelated,PROD)",
        ])
        scenarios = {item["id"]: item for item in resources if item["kind"] == "scenario"}
        self.assertEqual(["urn:li:dataset:(urn:li:dataPlatform:postgres,nyc_taxi_mart,PROD)"], scenarios["nyc-taxi"]["loaded_urns"])
        self.assertTrue(scenarios["nyc-taxi"]["reviewable"])
        self.assertEqual([], scenarios["healthcare"]["loaded_urns"])
        self.assertEqual("not_loaded", scenarios["healthcare"]["ingestion_status"])

    def test_fixture_discovery_lists_real_dataset_urns(self):
        state = ReviewState(
            "examples/policies/enterprise_ai.yml",
            datahub_url=None,
            datahub_file="examples/data/datahub_graph.json",
        )
        result = state.resources()
        self.assertTrue(result["discovered_dataset_urns"])
        self.assertIsNone(result["discovery_error"])
