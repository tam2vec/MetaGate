# Examples Index

Use these examples in the demo and submission.

## Data

- `data/datahub_graph.json`: local DataHub-shaped fixture for repeatable demos.

## Policies

- `policies/enterprise_ai.yml`: general AI readiness policy for the main demo.
- `policies/finance-production.yml`: stricter production finance policy.
- `policies/schema-change.yml`: focused policy for schema modification risk.
- `policies/discovery.yml`: lighter policy for discovery and explanation use.

## Outputs

- `outputs/certificate.json`: MetaGate Certificate.
- `outputs/context-contract.json`: AI Context Contract returned to an agent or
  written back to DataHub.
- `outputs/explainability-report.json`: evidence-to-policy-to-decision report.
- `outputs/blocked-action.json`: admission-control result for a risky action.
- `outputs/readiness-diff.json`: before/after capability movement.
- `outputs/policy-simulation.json`: current versus proposed policy behavior.
- `outputs/writeback-payload.json`: representative DataHub write-back body.

## Benchmark

- `benchmark/cases.json`: 30 curated labeled policy scenarios.
- `benchmark/heldout_template.json`: template for independent unseen cases.

## DataHub Skill Reference

- `datahub-ai-readiness-skill/`: installable reference plugin structure for a
  DataHub AI readiness skill.
- `datahub-embed/`: compact MetaGate side-panel prototype and JSON contract
  for a DataHub asset page integration.
- `datahub-preflight-action/`: Context Gradient Preflight action contract and
  AI Context Contract aspect shape.

Local outputs are generated from the bundled fixture. Use
`docs/live-datahub-validation.md` before describing any output as real
deployment evidence.
