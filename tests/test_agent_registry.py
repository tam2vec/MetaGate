import json
import tempfile
import unittest
from pathlib import Path

from metagate.agent_gate import ToolCallDenied, authorize_tool_call
from metagate.agent_registry import (
    DEFAULT_AGENT_URN,
    DEFAULT_SERVICE_URN,
    DEFAULT_SKILL_URN,
    DEFAULT_TOOL_URN,
    apply_agent_registry_gate,
    default_catalog,
    resolve_agent_context,
)
from metagate.contracts import build_constraint_contract


class AgentRegistryTest(unittest.TestCase):
    def test_default_chain_is_verified_for_requested_action(self):
        context = resolve_agent_context(dataset_urn="urn:li:dataset:test", requested=True)
        self.assertEqual(context["status"], "verified")
        self.assertEqual(context["agent_urn"], DEFAULT_AGENT_URN)
        self.assertEqual(context["skill_urn"], DEFAULT_SKILL_URN)
        self.assertEqual(context["tool_urn"], DEFAULT_TOOL_URN)
        self.assertEqual(context["service_urn"], DEFAULT_SERVICE_URN)

    def test_unrequested_chain_does_not_change_existing_decision(self):
        context = resolve_agent_context(dataset_urn="urn:li:dataset:test")
        self.assertEqual(context["status"], "not_requested")

    def test_scope_mismatch_blocks_and_explains_link_failure(self):
        catalog = default_catalog()
        catalog["agents"][0]["tools"] = []
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            path.write_text(json.dumps(catalog), encoding="utf-8")
            context = resolve_agent_context(registry_path=path, dataset_urn="urn:li:dataset:test", requested=True)
        self.assertEqual(context["status"], "scope_mismatch")
        self.assertTrue(any("not linked" in reason for reason in context["blocking_reasons"]))

    def test_skill_capability_scope_is_fail_closed(self):
        context = resolve_agent_context(
            dataset_urn="urn:li:dataset:test",
            requested=True,
        )
        self.assertEqual(context["status"], "verified")
        context = resolve_agent_context(
            dataset_urn="urn:li:dataset:test",
            requested=True,
            capability="delete-production-dataset",
        )
        self.assertEqual(context["status"], "scope_mismatch")
        self.assertTrue(any("does not authorize" in reason for reason in context["blocking_reasons"]))

    def test_gate_adds_registry_failure_to_metagate(self):
        decision = {
            "allowed": True,
            "decision": "allowed",
            "reason": "Capability is certified.",
            "action_metagate": {"result": True, "decision": "allowed", "failed_terms": []},
        }
        context = {"status": "unavailable", "blocking_reasons": ["registry lookup failed"]}
        apply_agent_registry_gate(decision, context, "autonomous-agent-action")
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["decision"], "blocked")
        self.assertIn("agent_registry.verified", decision["action_metagate"]["failed_terms"])

    def test_contract_carries_registry_chain(self):
        run = {
            "urn": "urn:li:dataset:test",
            "decision": "allowed",
            "allowed": True,
            "capability": "answer-business-questions",
            "decision_id": "pred-test",
            "evaluated_at": "2026-08-07T00:00:00+00:00",
            "agent_context": {
                "status": "verified",
                "agent_urn": DEFAULT_AGENT_URN,
                "skill_urn": DEFAULT_SKILL_URN,
                "tool_urn": DEFAULT_TOOL_URN,
                "service_urn": DEFAULT_SERVICE_URN,
            },
            "registry_required": True,
        }
        contract = build_constraint_contract(run)
        self.assertTrue(contract["registry_required"])
        self.assertEqual(contract["agent_context"]["status"], "verified")
        self.assertEqual(contract["agent_context"]["tool_urn"], DEFAULT_TOOL_URN)

    def test_tool_gate_requires_verified_registry_when_configured(self):
        contract = {
            "decision": "allowed",
            "allowed_action": "answer-business-questions",
            "permitted_datasets": ["urn:li:dataset:test"],
            "registry_required": True,
            "registry_evidence": {"status": "scope_mismatch", "blocking_reasons": ["wrong service"]},
            "agent_context": {"tool_urn": DEFAULT_TOOL_URN, "service_urn": DEFAULT_SERVICE_URN},
        }
        with self.assertRaises(ToolCallDenied):
            authorize_tool_call(
                contract,
                action="answer-business-questions",
                dataset_urn="urn:li:dataset:test",
                tool_urn=DEFAULT_TOOL_URN,
                service_urn=DEFAULT_SERVICE_URN,
            )


if __name__ == "__main__":
    unittest.main()
