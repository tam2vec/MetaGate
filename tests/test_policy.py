import unittest
from pathlib import Path

from context_gradient.sdk.models import EvidenceKind
from context_gradient.sdk.policy import load_policy


class PolicyTest(unittest.TestCase):
    def test_load_policy_profile(self):
        policy = load_policy(
            Path(__file__).resolve().parents[1] / "examples/policies/enterprise_ai.yml"
        )

        self.assertEqual(policy.name, "enterprise-ai")
        self.assertEqual(policy.evidence_weights[EvidenceKind.ASSERTIONS], 1.3)
        self.assertEqual(policy.capability_policies[0].name, "answer-business-questions")


if __name__ == "__main__":
    unittest.main()
