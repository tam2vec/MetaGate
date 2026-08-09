"""Checks against the GraphQL shapes used by a real DataHub deployment.

The live test is opt-in because the repository must remain runnable without a
DataHub server. Set DATAHUB_GRAPHQL_URL and METAGATE_LIVE_DATAHUB_URN to run
it against the deployment used for a demo.
"""

from __future__ import annotations

import os
import unittest

from context_gradient.datahub.adapter import GraphQLDataHubClient


class DataHubSchemaContractTest(unittest.TestCase):
    def test_query_requests_real_quality_and_incident_facts(self):
        query = GraphQLDataHubClient.QUERY
        self.assertIn("assertions(start: 0, count: 100)", query)
        self.assertIn("runEvents(limit: 100)", query)
        self.assertIn("timestampMillis", query)
        self.assertIn("result { type", query)
        self.assertIn("incidents(state: ACTIVE", query)
        self.assertIn("status { state }", query)
        self.assertIn("schemaMetadata", GraphQLDataHubClient.OPTIONAL_QUERIES["schema"])

    def test_optional_schema_failure_does_not_hide_other_evidence(self):
        urn = "urn:li:dataset:(urn:li:dataPlatform:hive,sample,PROD)"

        class PartiallySupportedClient(GraphQLDataHubClient):
            def _request(self, query, variables):
                if "ContextGradientCore" in query:
                    return {"dataset": {"urn": variables["urn"], "properties": {"description": "sample"}}}
                if "ContextGradientAssertions" in query:
                    return {"dataset": {"assertions": {"assertions": [{"urn": "urn:li:assertion:row-count"}]}}}
                raise RuntimeError('FieldUndefined: optional field is not exposed')

        entity = PartiallySupportedClient("http://datahub.invalid").get_entity(urn)
        self.assertEqual(entity["assertions"]["names"][0], "urn:li:assertion:row-count")
        self.assertIn("assertions", entity["_available_evidence"])
        self.assertIn("incidents", entity["_unavailable_evidence"])
        self.assertIn("usage", entity["_unavailable_evidence"])

    def test_normalize_accepts_named_owner_and_term_shapes(self):
        client = GraphQLDataHubClient("http://datahub.invalid")
        entity = client._normalize(
            {
                "urn": "urn:li:dataset:(urn:li:dataPlatform:hive,sample,PROD)",
                "properties": {"description": "sample"},
                "ownership": {"owners": [{"owner": {"username": "alice"}}]},
                "glossaryTerms": {"terms": [{"term": {"name": "Customer"}}]},
                "domain": {"domain": {"name": "Finance"}},
                "tags": {"tags": [{"tag": {"name": "production"}}]},
            },
            "urn:li:dataset:(urn:li:dataPlatform:hive,sample,PROD)",
        )
        self.assertEqual(entity["ownership"]["owners"], ["alice"])
        self.assertEqual(entity["glossary"]["terms"], ["Customer"])
        self.assertEqual(entity["domain"]["urn"], "Finance")
        self.assertIn("ownership", entity["_available_evidence"])
        self.assertIn("glossary", entity["_available_evidence"])

    def test_core_schema_failure_falls_back_to_minimal_entity_read(self):
        urn = "urn:li:dataset:(urn:li:dataPlatform:hive,sample,PROD)"

        class MinimalFallbackClient(GraphQLDataHubClient):
            def _request(self, query, variables):
                if "ContextGradientCore" in query:
                    raise RuntimeError("FieldUndefined: deployment-specific field")
                if "ContextGradientEntity" in query:
                    return {"dataset": {"urn": variables["urn"], "properties": {"description": "sample"}}}
                raise RuntimeError("FieldUndefined: optional field is not exposed")

        entity = MinimalFallbackClient("http://datahub.invalid").get_entity(urn)
        self.assertEqual(entity["urn"], urn)
        self.assertEqual(entity["description"]["text"], "sample")
        self.assertIn("ownership", entity["_unavailable_evidence"])
        self.assertIn("glossary", entity["_unavailable_evidence"])


@unittest.skipUnless(
    os.environ.get("DATAHUB_GRAPHQL_URL") and os.environ.get("METAGATE_LIVE_DATAHUB_URN"),
    "set DATAHUB_GRAPHQL_URL and METAGATE_LIVE_DATAHUB_URN for a live DataHub check",
)
class LiveDataHubSchemaIntegrationTest(unittest.TestCase):
    def test_deployment_returns_a_dataset_shape(self):
        client = GraphQLDataHubClient(os.environ["DATAHUB_GRAPHQL_URL"])
        entity = client.get_entity(os.environ["METAGATE_LIVE_DATAHUB_URN"])
        self.assertEqual(entity["urn"], os.environ["METAGATE_LIVE_DATAHUB_URN"])
        self.assertIn("ownership", entity)
        self.assertIn("assertions", entity)
        self.assertIn("incidents", entity)
        self.assertIn("_available_evidence", entity)
        self.assertIn("_unavailable_evidence", entity)
        self.assertIn("_datahub_observation", entity["properties"])


if __name__ == "__main__":
    unittest.main()
