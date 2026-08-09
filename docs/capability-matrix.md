# Capability Matrix

MetaGate certifies actions, not a single global “AI ready” label. Each
capability is gated by the metadata evidence named in its active policy.

| Capability | Required metadata | Example status |
| --- | --- | --- |
| Answer business questions | Ownership, glossary, freshness, policy | Certified under `enterprise-ai` when thresholds pass |
| Generate executive metrics | Ownership, glossary, lineage, assertions, freshness, policy | Certified only when quality evidence is current |
| Autonomous agent action | Ownership, glossary, lineage, assertions, incidents, freshness, usage, policy | High threshold and confidence required |
| Rename column | Ownership, column lineage, downstream consumers, policy | Blocked by `schema-change-control` until impact is known |
| Approve schema migration | Ownership, column lineage, downstream consumers, assertions, incidents, policy | Highest-risk gate |

The matrix is policy-driven. Teams can add capabilities and evidence rules in
YAML without changing the scoring engine.
