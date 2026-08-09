# Screenshots Checklist

Capture these before the final demo upload. Use neutral sample metadata and
redact tokens, private hostnames, and customer data.

| Order | Screenshot | Purpose |
| ---: | --- | --- |
| 1 | README top section | Shows name, claim, badges, and architecture. |
| 2 | DataHub asset before repair | Shows the real asset URN and baseline metadata. |
| 3 | Baseline MetaGate Certificate | Shows capabilities, score, gaps, and timestamp. |
| 4 | Blocked risky action | Shows admission control with `allowed: false`. |
| 5 | Explainability report | Shows deterministic evidence-to-policy-to-decision path. |
| 6 | Metadata repair in DataHub | Shows owner, glossary, assertion, or lineage change. |
| 7 | DataHub event or ingestion timestamp | Proves the change came from metadata, not prompt editing. |
| 8 | Updated MetaGate Certificate | Shows recomputation after repair. |
| 9 | Readiness diff | Shows before/after capability movement. |
| 10 | Write-back result | Shows certificate or remediation task in DataHub, if enabled. |
| 11 | Benchmark result | Shows 30 curated conformance checks passing with no unexpected allows or blocks. |
| 12 | Upstream contribution bundle | Shows DataHub PR-ready files. |

Keep fixture screenshots separate from live deployment screenshots. Label them
as rehearsal artifacts in the submission if they are used.
