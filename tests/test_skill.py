import unittest
from pathlib import Path

from context_gradient.skill import _decision_payload, certify

ROOT = Path(__file__).resolve().parents[1]


def certificate(*, allowed_capabilities=None, latest_results=None, freshness=None):
    allowed_capabilities = allowed_capabilities or ["answer-business-questions"]
    return {
        "entity_urn": "urn:test:dataset",
        "context_contract": {
            "allowed_capabilities": allowed_capabilities,
            "verified_claims": ["owner", "lineage"],
        },
        "certified_capabilities": [
            {"capability": item, "certified": True, "reasons": []}
            for item in allowed_capabilities
        ],
        "metadata": {
            "assessment": {
                "facts": {
                    "owner": "data-team",
                    "assertions": {"latest_results": latest_results or []},
                    "freshness": freshness or {},
                }
            }
        },
        "gaps": [],
        "recommendations": [],
    }


class SkillContractTest(unittest.TestCase):
    def test_skill_can_run_against_a_local_graph(self):
        result = certify(
            "urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)",
            "examples/policies/enterprise_ai.yml",
            datahub_file="examples/data/six_asset_review_graph.json",
            capability="answer-business-questions",
        )
        self.assertEqual(result["entity_urn"], "urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)")
        self.assertIn(result["decision"], {"allowed", "blocked"})
        self.assertEqual(result["constraint_contract"]["contract_version"], "1.0")

    def test_skill_contract_uses_shared_action_guardrail(self):
        payload = certificate(
            allowed_capabilities=["generate-executive-metrics"],
            latest_results=[
                {"name": "daily_row_count", "status": "FAILURE", "timestamp": 42}
            ],
            freshness={"timestamp": "2026-08-05T00:00:00Z"},
        )

        decision = _decision_payload(payload, "generate-executive-metrics")

        self.assertEqual(decision["decision"], "blocked")
        self.assertIn("daily_row_count", decision["reason"])
        self.assertEqual(decision["constraint_contract"]["decision"], "blocked")
        self.assertEqual(
            decision["constraint_contract"]["evidence"]["assertions"]["result_state"],
            "failing",
        )
        self.assertEqual(decision["constraint_contract"]["evidence"]["owner"]["value"], "data-team")

    def test_skill_contract_marks_high_impact_allowed_action_for_approval(self):
        payload = certificate(
            allowed_capabilities=["autonomous-agent-action"],
            latest_results=[{"name": "quality", "status": "SUCCESS", "timestamp": 42}],
            freshness={"timestamp": "2026-08-05T00:00:00Z"},
        )

        decision = _decision_payload(payload, "autonomous-agent-action")

        self.assertEqual(decision["decision"], "allowed")
        contract = decision["constraint_contract"]
        self.assertTrue(contract["required_human_approval"])
        self.assertEqual(contract["blocking_reasons"], [])
        self.assertIn("autonomous-agent-action", contract["allowed_action"])


if __name__ == "__main__":
    unittest.main()
