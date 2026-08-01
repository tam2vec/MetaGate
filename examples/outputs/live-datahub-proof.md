# Live DataHub Proof

Predicate was run against a local DataHub quickstart seeded with sample metadata.
The same policy produced different decisions for different DataHub assets.

| Asset | Capability | Decision | Reason |
| --- | --- | --- | --- |
| `SampleHiveDataset` | `autonomous-agent-action` | allowed | Capability is certified by the active policy. |
| `fct_users_created` | `autonomous-agent-action` | blocked | Missing assertions; readiness score below 92.0; confidence below 88.0. |
| `fct_users_deleted` | `autonomous-agent-action` | blocked | Missing assertions; readiness score below 92.0; confidence below 88.0. |

This proves Predicate is not a static checklist or blanket blocker. It turns the
DataHub metadata graph into per-asset, per-capability go/no-go decisions.
