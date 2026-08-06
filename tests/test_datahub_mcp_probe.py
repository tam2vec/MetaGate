import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from predicate.datahub_mcp_probe import DataHubMCPProbe
from predicate.mcp_evidence import normalize_mcp_entity_output, normalize_mcp_query_output


class DataHubMCPProbeTest(unittest.TestCase):
    def test_unconfigured_probe_does_not_start_a_process(self):
        result = DataHubMCPProbe("").run("urn:test:asset")
        self.assertEqual(result["status"], "not_configured")

    def test_probe_handshakes_lists_tools_and_reads_entity(self):
        with tempfile.TemporaryDirectory() as directory:
            server = Path(directory) / "fake_mcp.py"
            server.write_text(textwrap.dedent(
                """
                import json, sys
                def read():
                    headers = {}
                    while True:
                        line = sys.stdin.buffer.readline()
                        if line in (b'\\r\\n', b'\\n'):
                            break
                        key, _, value = line.decode().partition(':')
                        headers[key.lower()] = value.strip()
                    return json.loads(sys.stdin.buffer.read(int(headers['content-length'])))
                def send(value):
                    data = json.dumps(value, separators=(',', ':')).encode()
                    sys.stdout.buffer.write(b'Content-Length: ' + str(len(data)).encode() + b'\\r\\n\\r\\n' + data)
                    sys.stdout.buffer.flush()
                while True:
                    request = read()
                    if request.get('id') is None:
                        continue
                    method = request.get('method')
                    if method == 'initialize':
                        result = {'serverInfo': {'name': 'fake-datahub-mcp', 'version': 'test'}}
                    elif method == 'tools/list':
                        result = {'tools': [
                            {'name': 'search', 'inputSchema': {'properties': {}}},
                            {'name': 'get_entities', 'inputSchema': {'properties': {'urns': {'type': 'array'}}}},
                            {'name': 'get_lineage', 'inputSchema': {'properties': {}}},
                            {'name': 'list_schema_fields', 'inputSchema': {'properties': {}}},
                            {'name': 'get_dataset_queries', 'inputSchema': {'properties': {'dataset_urn': {'type': 'string'}}}},
                        ]}
                    elif method == 'tools/call':
                        if request['params']['name'] == 'get_dataset_queries':
                            result = {'content': [{'type': 'text', 'text': json.dumps({
                                'queries': [{'executedAt': '2026-08-05T12:00:00Z', 'queryText': 'SELECT secret FROM private_table'}]
                            })}]}
                        else:
                            result = {'content': [{'type': 'text', 'text': json.dumps({
                                'entities': [{
                                'urn': 'urn:test:asset',
                                'type': 'dataset',
                                'description': {'text': 'A tested dataset'},
                                'ownership': {'owners': [{'owner': {'urn': 'urn:li:corpuser:steward'}}]},
                                'glossaryTerms': {'terms': [{'term': {'urn': 'urn:li:glossaryTerm:revenue'}}]},
                                'upstreamLineage': {'upstreams': [{'entity': {'urn': 'urn:test:source'}}]},
                                'downstreamLineage': {'downstreams': [{'entity': {'urn': 'urn:test:dashboard'}}]},
                                'schemaMetadata': {'fields': [{'fieldPath': 'id'}]},
                                'assertions': {'assertions': [{'urn': 'urn:test:assertion', 'runEvents': {'runEvents': [{'status': 'SUCCESS', 'timestampMillis': 1700000000000}]}}]},
                                'freshness': {'timestamp': '2026-08-05T12:00:00Z', 'sla': '24h'},
                                'incidents': {'incidents': []},
                                }]
                            })}]}
                    else:
                        result = {}
                    send({'jsonrpc': '2.0', 'id': request['id'], 'result': result})
                """
            ))
            result = DataHubMCPProbe(f"{sys.executable} {server}").run("urn:test:asset")
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["entity_call"]["status"], "ok")
        self.assertEqual(result["entity_call"]["argument_shape"], ["urns"])
        self.assertEqual(result["server_info"]["name"], "fake-datahub-mcp")
        self.assertTrue(result["entity_call"]["entity_found"])
        self.assertEqual(result["entity_call"]["facts"]["ownership"]["owners"], ["urn:li:corpuser:steward"])
        self.assertEqual(result["entity_call"]["facts"]["lineage"]["upstreams"], ["urn:test:source"])
        self.assertEqual(result["entity_call"]["facts"]["assertions"]["latest_results"][0]["status"], "SUCCESS")
        self.assertEqual(result["entity_call"]["evidence"]["incidents"]["status"], "clear")
        self.assertEqual(result["query_call"]["status"], "present")
        self.assertEqual(result["query_call"]["query_count"], 1)
        self.assertEqual(result["query_call"]["latest_query_at"], "2026-08-05T12:00:00Z")
        self.assertNotIn("secret", json.dumps(result["query_call"]))

    def test_normalizer_rejects_unparseable_or_wrong_asset_content(self):
        result = normalize_mcp_entity_output(
            {"content": [{"type": "text", "text": "not JSON"}]},
            "urn:test:asset",
        )
        self.assertEqual(result["status"], "attention_required")
        self.assertFalse(result["entity_found"])
        self.assertIn("not treated as evidence", result["notes"][0])

    def test_normalizer_reports_unavailable_fields_and_column_gaps(self):
        urn = "urn:test:asset"
        result = normalize_mcp_entity_output(
            {
                "structuredContent": {
                    "entities": [{
                        "urn": urn,
                        "schemaMetadata": {"fields": [{"fieldPath": "id"}, {"fieldPath": "email"}]},
                        "fineGrainedLineages": {"fineGrainedLineages": [{"downstreams": [{"fieldPath": "id"}]}]},
                    }]
                }
            },
            urn,
        )
        self.assertEqual(result["evidence"]["ownership"]["status"], "unavailable")
        self.assertEqual(result["evidence"]["assertions"]["status"], "unavailable")
        self.assertEqual(result["facts"]["column_lineage"]["missing_columns"], ["email"])

    def test_query_normalizer_distinguishes_empty_from_unavailable(self):
        self.assertEqual(
            normalize_mcp_query_output({"structuredContent": {"queries": []}})["status"],
            "absent",
        )
        self.assertEqual(normalize_mcp_query_output({"structuredContent": {}})["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
