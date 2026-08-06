import unittest

from context_gradient.sdk.admission import enforce_action_guardrails
from predicate.contracts import build_constraint_contract


def certificate(*, latest_results=None, freshness=None, allowed=None):
    allowed = allowed or ["answer-business-questions", "generate-executive-metrics"]
    return {
        "entity_urn": "urn:test:dataset",
        "context_contract": {"allowed_capabilities": allowed, "verified_claims": ["owner"]},
        "certified_capabilities": [
            {"capability": item, "certified": True, "reasons": []} for item in allowed
        ],
        "metadata": {
            "assessment": {
                "facts": {
                    "assertions": {"latest_results": latest_results or []},
                    "freshness": freshness or {},
                }
            }
        },
    }


class ActionGuardrailTest(unittest.TestCase):
    def test_explanation_can_use_base_policy_decision(self):
        decision = enforce_action_guardrails(certificate(), "answer-business-questions")
        self.assertTrue(decision.allowed)

    def test_modification_requires_steward_and_write_adapter(self):
        decision = enforce_action_guardrails(certificate(), "modify-dataset")
        self.assertFalse(decision.allowed)
        self.assertIn("steward approval", decision.reason)
        self.assertIn("write adapter", decision.reason)

    def test_restricted_sql_requires_verified_scope(self):
        decision = enforce_action_guardrails(certificate(), "restricted-sql")
        self.assertFalse(decision.allowed)
        self.assertIn("column scope", decision.reason)

    def test_executive_metrics_requires_latest_passing_assertion_and_freshness(self):
        result = enforce_action_guardrails(
            certificate(
                latest_results=[
                    {"name": "daily_row_count", "status": "SUCCESS", "timestamp": 20}
                ],
                freshness={"timestamp": "2026-08-05T00:00:00Z"},
            ),
            "generate-executive-metrics",
        )
        self.assertTrue(result.allowed)

    def test_executive_metrics_blocks_without_latest_assertion(self):
        result = enforce_action_guardrails(
            certificate(freshness={"timestamp": "2026-08-05T00:00:00Z"}),
            "generate-executive-metrics",
        )
        self.assertFalse(result.allowed)
        self.assertIn("latest assertion result", result.reason)

    def test_executive_metrics_names_failed_assertion_and_time(self):
        result = enforce_action_guardrails(
            certificate(
                latest_results=[
                    {"name": "daily_row_count", "status": "FAILURE", "timestamp": 42}
                ],
                freshness={"timestamp": "2026-08-05T00:00:00Z"},
            ),
            "generate-executive-metrics",
        )
        self.assertFalse(result.allowed)
        self.assertIn("daily_row_count", result.reason)
        self.assertIn("42", result.reason)

    def test_constraint_contract_preserves_latest_evidence_facts(self):
        run = {
            "urn": "urn:test:dataset",
            "capability": "answer-business-questions",
            "decision": "allowed",
            "allowed": True,
            "facts": {
                "owner": "alice",
                "glossary_terms": ["Customer"],
                "lineage": {"upstream_count": 1, "downstream_count": 2},
                "assertions": {
                    "latest_results": [
                        {"name": "row_count", "status": "SUCCESS", "timestamp": 2}
                    ]
                },
                "freshness": {"timestamp": "2026-08-05T00:00:00Z"},
                "column_lineage": {"mapping_count": 2, "missing_columns": []},
            },
        }
        contract = build_constraint_contract(run)
        self.assertEqual(contract["evidence"]["owner"]["value"], "alice")
        self.assertEqual(contract["evidence"]["glossary"]["terms"], ["Customer"])
        self.assertEqual(contract["evidence"]["assertions"]["latest_result"]["name"], "row_count")
        self.assertEqual(contract["evidence"]["freshness"]["timestamp"], "2026-08-05T00:00:00Z")

    def test_allowed_contract_does_not_call_success_a_blocking_reason(self):
        run = {
            "urn": "urn:test:dataset",
            "capability": "answer-business-questions",
            "decision": "allowed",
            "allowed": True,
            "reason": "Capability is certified by the active policy.",
        }
        contract = build_constraint_contract(run)
        self.assertEqual(contract["blocking_reasons"], [])
        self.assertEqual(contract["decision_basis"], "Capability is certified by the active policy.")

    def test_high_impact_allowed_contract_still_requires_approval(self):
        run = {
            "urn": "urn:test:dataset",
            "capability": "autonomous-agent-action",
            "decision": "allowed",
            "allowed": True,
        }
        contract = build_constraint_contract(run)
        self.assertTrue(contract["required_human_approval"])
        self.assertIn("high-impact", contract["approval_reason"])
        self.assertEqual(contract["blocking_reasons"], [])

    def test_contract_distinguishes_incomplete_assertions_from_a_failed_result(self):
        incomplete = build_constraint_contract({
            "urn": "urn:test:dataset",
            "decision": "blocked",
            "allowed": False,
            "facts": {"assertions": {}},
            "score_trace": {"evidence": [{"kind": "assertions", "state": "present"}]},
        })
        self.assertEqual(incomplete["evidence"]["assertions"]["status"], "incomplete")
        self.assertEqual(incomplete["evidence"]["assertions"]["result_state"], "unavailable")

        failed = build_constraint_contract({
            "urn": "urn:test:dataset",
            "decision": "blocked",
            "allowed": False,
            "facts": {"assertions": {"latest_results": [{"name": "row_count", "status": "FAILURE"}]}},
            "score_trace": {"evidence": [{"kind": "assertions", "state": "present"}]},
        })
        self.assertEqual(failed["evidence"]["assertions"]["status"], "present")
        self.assertEqual(failed["evidence"]["assertions"]["result_state"], "failing")

    def test_contract_reports_clear_incidents_and_partial_lineage(self):
        contract = build_constraint_contract({
            "urn": "urn:test:dataset",
            "decision": "allowed",
            "allowed": True,
            "facts": {
                "incidents": {"open": 0},
                "lineage": {"coverage": 0.5},
            },
            "score_trace": {"evidence": [
                {"kind": "incidents", "state": "present"},
                {"kind": "lineage", "state": "present"},
            ]},
        })
        self.assertEqual(contract["evidence"]["incidents"]["status"], "clear")
        self.assertEqual(contract["evidence"]["lineage"]["status"], "partial")


if __name__ == "__main__":
    unittest.main()
