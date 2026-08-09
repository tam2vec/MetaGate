# DataHub-Shaped Fixture Proof

This is a deterministic DataHub-shaped fixture proof. It is not a claim that
the current connected local DataHub returned these same results. The same
policy produces different decisions for different fixture assets.

| Asset | Capability | Decision | Reason |
| --- | --- | --- | --- |
| `SampleHiveDataset` | `autonomous-agent-action` | allowed | Capability is certified by the active policy. |
| `fct_users_created` | `autonomous-agent-action` | blocked | Missing assertions; readiness score below 92.0; confidence below 88.0. |
| `fct_users_deleted` | `autonomous-agent-action` | blocked | Missing assertions; readiness score below 92.0; confidence below 88.0. |

This proves MetaGate is not a static checklist or blanket blocker. It turns the
DataHub metadata graph into per-asset, per-capability go/no-go decisions.
