import unittest

from metagate.adversarial_scenarios import generate_scenarios
from metagate.agent_gate import ToolCallDenied, guarded_tool_call
from metagate.incident_investigator import investigate
from metagate.repair_loop import run_repair_loop


class ProofLayersTest(unittest.TestCase):
    def test_adversarial_generator_covers_required_categories(self):
        scenarios = generate_scenarios(count_per_category=5)
        self.assertGreaterEqual(len(scenarios), 50)
        categories = {item["category"] for item in scenarios}
        self.assertTrue({
            "prompt_injection",
            "restricted_columns",
            "stale_metadata",
            "failed_assertion",
            "conflicting_owners",
            "tool_failure",
        }.issubset(categories))

    def test_blocked_contract_never_calls_tool(self):
        calls = []
        contract = {
            "decision": "blocked",
            "decision_id": "pred-test-blocked",
            "blocking_reasons": ["assertions.present"],
        }
        with self.assertRaises(ToolCallDenied):
            guarded_tool_call(
                contract,
                action="answer-business-questions",
                dataset_urn="urn:li:dataset:test",
                tool=lambda: calls.append("called"),
            )
        self.assertEqual(calls, [])

    def test_allowed_contract_calls_tool_in_scope(self):
        contract = {
            "decision": "allowed",
            "decision_id": "pred-test-allowed",
            "allowed_action": "answer-business-questions",
            "permitted_datasets": ["urn:li:dataset:test"],
            "permitted_columns": ["customer_id"],
        }
        result = guarded_tool_call(
            contract,
            action="answer-business-questions",
            dataset_urn="urn:li:dataset:test",
            tool=lambda: {"executed": True},
        )
        self.assertEqual(result, {"executed": True})

    def test_incident_investigator_identifies_failing_upstream(self):
        run = {
            "entity_urn": "urn:li:dataset:downstream",
            "facts": {
                "lineage": {"upstreams": [{"urn": "urn:li:dataset:upstream"}], "downstreams": []},
                "incidents": {
                    "open": 1,
                    "items": [{
                        "urn": "urn:li:incident:row-count",
                        "entity_urn": "urn:li:dataset:upstream",
                        "signal": "assertions",
                        "message": "daily_row_count failed",
                        "status": "OPEN",
                        "observed_at": "2026-08-07T00:00:00Z",
                    }],
                },
            },
        }
        result = investigate(run)
        self.assertEqual(result["status"], "investigation_required")
        self.assertEqual(result["root_cause"]["asset"], "urn:li:dataset:upstream")
        self.assertIn("daily_row_count", result["root_cause"]["fact"])

    def test_repair_loop_polls_then_rechecks(self):
        polls = []
        result = run_repair_loop(
            {"entity_urn": "urn:li:dataset:test", "decision": "blocked", "readiness": 61.0, "failed": ["freshness.present"]},
            repair=lambda: {"status": "applied", "applied": True, "change": "freshness SLA repaired"},
            poll=lambda attempt: polls.append(attempt) or ({"status": "waiting", "readable": False} if attempt == 1 else {"status": "ready", "readable": True, "source_observed_at": "2026-08-07T00:01:00Z"}),
            evaluate=lambda: {"decision": "allowed", "readiness": 96.0, "confidence": 94.0, "failed": []},
            decision_id="pred-test-repair",
        )
        self.assertEqual(result["status"], "repaired")
        self.assertEqual(polls, [1, 2])
        self.assertEqual(result["score_delta"], 35.0)
        self.assertEqual([event["event_type"] for event in result["audit_events"]], [
            "before_evaluation", "repair_applied", "indexing_poll", "indexing_poll", "after_evaluation",
        ])


if __name__ == "__main__":
    unittest.main()
