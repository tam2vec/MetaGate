import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def frame(value):
    encoded = json.dumps(value, separators=(",", ":")).encode("utf-8")
    return b"Content-Length: " + str(len(encoded)).encode("ascii") + b"\r\n\r\n" + encoded


def read_frame(stream):
    headers = {}
    while True:
        line = stream.readline()
        if not line:
            raise AssertionError("MCP server closed before replying")
        if line in (b"\r\n", b"\n"):
            break
        key, value = line.decode().split(":", 1)
        headers[key.lower()] = value.strip()
    size = int(headers["content-length"])
    return json.loads(stream.read(size))


class MCPServerTest(unittest.TestCase):
    def test_server_advertises_predicate_tools(self):
        process = subprocess.Popen(
            [sys.executable, "-m", "predicate.mcp_server", "--policy", "examples/policies/enterprise_ai.yml"],
            cwd=ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            process.stdin.write(frame({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}))
            process.stdin.write(frame({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}))
            process.stdin.flush()
            initialize = read_frame(process.stdout)
            tools = read_frame(process.stdout)
            self.assertEqual(initialize["result"]["serverInfo"]["name"], "predicate")
            names = {item["name"] for item in tools["result"]["tools"]}
            self.assertEqual(names, {"predicate_evaluate", "predicate_constraint_contract", "predicate_evidence"})
        finally:
            process.stdin.close()
            process.stdout.close()
            process.stderr.close()
            process.kill()
            process.wait()

    def test_mcp_evaluates_a_local_graph_with_the_shared_guardrail(self):
        from predicate.mcp_server import PredicateMCP

        server = PredicateMCP(
            "examples/policies/enterprise_ai.yml",
            None,
            None,
            "examples/data/six_asset_review_graph.json",
        )
        result = server.call("predicate_evaluate", {
            "urn": "urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)",
            "capability": "modify-dataset",
        })
        self.assertEqual(result["decision"], "blocked")
        self.assertEqual(result["constraint_contract"]["contract_version"], "1.0")
        self.assertIn("modify-dataset", result["constraint_contract"]["forbidden_actions"])


if __name__ == "__main__":
    unittest.main()
