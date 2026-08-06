import unittest

from predicate.hackathon_resources import resource_catalog
from predicate.review import ReviewState


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

    def test_fixture_discovery_lists_real_dataset_urns(self):
        state = ReviewState(
            "examples/policies/enterprise_ai.yml",
            datahub_url=None,
            datahub_file="examples/data/datahub_graph.json",
        )
        result = state.resources()
        self.assertTrue(result["discovered_dataset_urns"])
        self.assertIsNone(result["discovery_error"])
