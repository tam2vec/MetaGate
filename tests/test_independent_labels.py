from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class IndependentLabelScorerTest(unittest.TestCase):
    def test_independent_label_report_counts_agreement(self):
        with tempfile.TemporaryDirectory() as directory:
            labels = Path(directory) / "labels.csv"
            output = Path(directory) / "report.json"
            labels.write_text(
                "asset_urn,predicate_decision,human_decision,human_agrees,reviewer_notes\n"
                "urn:one,allowed,allowed,yes,looks right\n"
                "urn:two,blocked,allowed,no,too strict\n"
            )
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/evaluate_independent_labels.py"),
                    "--labels",
                    str(labels),
                    "--output",
                    str(output),
                ],
                check=True,
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            report = json.loads(output.read_text())
            self.assertEqual(report["completed_labels"], 2)
            self.assertEqual(report["matches"], 1)
            self.assertEqual(report["disagreements"], 1)
            self.assertEqual(report["agreement_rate"], 0.5)

    def test_borderline_is_evaluated_as_a_safety_block(self):
        with tempfile.TemporaryDirectory() as directory:
            labels = Path(directory) / "labels.csv"
            output = Path(directory) / "report.json"
            labels.write_text(
                "asset_urn,predicate_decision,human_decision,human_agrees,reviewer_notes\n"
                "urn:one,blocked,borderline,yes,uncertain evidence\n"
            )
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/evaluate_independent_labels.py"),
                    "--labels", str(labels), "--output", str(output),
                ],
                check=True,
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            report = json.loads(output.read_text())
            self.assertEqual(report["matches"], 1)
            self.assertEqual(report["decision_rows"][0]["human_decision"], "blocked")


if __name__ == "__main__":
    unittest.main()
