import unittest

from metagate.datahub_action import handle_action, validate_action_request


class DataHubActionContractTest(unittest.TestCase):
    def test_request_accepts_datahub_event_field_names(self):
        self.assertEqual(
            validate_action_request(
                {"entityUrn": "urn:dataset:one", "capability": "answer-business-questions"}
            ),
            ("urn:dataset:one", "answer-business-questions"),
        )
        self.assertEqual(
            validate_action_request(
                {"urn": "urn:dataset:two", "action": "generate-executive-metrics"}
            ),
            ("urn:dataset:two", "generate-executive-metrics"),
        )

    def test_request_rejects_missing_identity_or_capability(self):
        with self.assertRaisesRegex(ValueError, "entityUrn"):
            validate_action_request({"capability": "answer-business-questions"})
        with self.assertRaisesRegex(ValueError, "capability"):
            validate_action_request({"entityUrn": "urn:dataset:one"})

    def test_action_returns_human_reasons_and_machine_failed_terms(self):
        result = handle_action(
            {"entityUrn": "urn:dataset:one", "capability": "modify-dataset"},
            lambda _urn, _capability: {
                "decision": "blocked",
                "allowed": False,
                "decision_id": "dec-123",
                "evaluated_at": "2026-08-07T00:00:00Z",
                "failed": ["assertions.present"],
                "constraint_contract": {
                    "contract_version": "metagate.ai-context-contract/v1",
                    "blocking_reasons": [
                        "The latest required assertion `row_count` failed at 2026-08-06T23:00:00Z."
                    ],
                },
            },
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["decision"], "blocked")
        self.assertEqual(result["blocking_reasons"], [
            "The latest required assertion `row_count` failed at 2026-08-06T23:00:00Z."
        ])
        self.assertEqual(result["failed_terms"], ["assertions.present"])
        self.assertEqual(result["writeback"], "read_only")


if __name__ == "__main__":
    unittest.main()
