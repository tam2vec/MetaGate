# Three-Minute Demo Script

Use a real DataHub deployment for the final recording. The bundled fixture is
only a rehearsal path and must be described as local rehearsal evidence.

## Screen setup

- Browser tab 1: DataHub asset page for the demo dataset.
- Browser tab 2: `examples/outputs/predicate-demo-app.html`.
- Browser tab 3: repository `README.md`.
- Terminal tab 1: Predicate CLI.
- Terminal tab 2: benchmark command/result.
- Finder or editor: `examples/outputs/` for backup artifacts.

## 0:00-0:20: Problem

Screen: DataHub asset page.

Narration:

“Enterprise AI agents can already query metadata catalogs. The missing control
is knowing whether the metadata is complete enough to trust an agent with a
specific action. Reading a dashboard is different from renaming a production
revenue column.”

## 0:20-0:40: Product

Screen: Predicate Review page, then repository README.

Narration:

“Predicate is an AI admission controller for metadata. It does not make AI
smarter. It determines when AI is allowed to act by turning DataHub evidence
into go/no-go decisions.”

Show the embedded DataHub-style panel first. Say:

“In the product experience, users should not read terminal JSON. The compact
Predicate panel appears beside the DataHub asset. If they need proof, they open
the full review.”

Command to show:

```bash
predicate \
  "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)" \
  --policy examples/policies/enterprise_ai.yml \
  --datahub-url "$DATAHUB_GRAPHQL_URL"
```

## 0:40-1:15: Block a risky action

Screen: terminal result for a risky capability request.

Command to show:

```bash
predicate \
  "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)" \
  --policy examples/policies/enterprise_ai.yml \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --request-capability autonomous-agent-action
```

Narration:

“Here the agent asks for autonomous action. Predicate blocks it. The decision is
deterministic: the certificate is not just a score, it names the missing or
stale evidence, the policy requirement, and the capabilities still allowed.”

Action predicate to show:

```json
{
  "action": "autonomous-agent-action",
  "predicate": "ownership.present && glossary.present && lineage.present && assertions.present && incidents.open == 0 && freshness.present && usage.present && policy.present",
  "result": false,
  "failed_terms": ["assertions.present"],
  "decision": "blocked"
}
```

Show:

- `allowed: false`
- blocked capability
- evidence gaps
- downstream or policy risk

## 1:15-1:45: Explain the decision

Screen: Predicate Review full section, then explainability output.

Command to show:

```bash
predicate \
  "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)" \
  --policy examples/policies/enterprise_ai.yml \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --explain
```

Narration:

“This is the evidence-to-policy-to-decision path. The system checks ownership,
glossary terms, lineage, assertions, freshness, incidents, usage, and policy
tags. It then certifies safe capabilities and blocks the rest.”

## 1:45-2:15: Repair metadata

Screen: Predicate Review page showing one blocked asset and one allowed asset.

Narration:

“The demo shows the before and after shape: one DataHub asset is blocked because
assertions are missing, while another asset with the required evidence is
allowed. Predicate treats this as a metadata problem, not a prompt problem.”

Evidence to show:

- same DataHub asset URN
- blocked reason
- allowed comparison asset

## 2:15-2:40: Reassess automatically

Screen: second CLI run, visual review, and readiness diff.

Command to show:

```bash
predicate \
  "urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)" \
  --policy examples/policies/enterprise_ai.yml \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --request-capability autonomous-agent-action
```

Narration:

“The scanner recomputes the affected asset and emits a readiness diff. The
important result is not that every action becomes allowed. The result is that
the allowed actions change only when the underlying evidence changes.”

Show:

- before certificate
- after certificate
- readiness diff
- updated context contract
- write-back receipt or confirmation if enabled

## 2:40-3:00: Close with proof

Screen: benchmark result, README, DataHub embed prototype, contribution bundle.

Command to show:

```bash
PYTHONPATH=src python3 scripts/evaluate_benchmark.py
```

Narration:

“The SDK is installable, policy-driven, and prepared as a DataHub contribution.
The curated 30-case conformance suite passes with no unexpected allows or
blocks. That is engineering validation of the policy behavior, not a production
accuracy claim. The product path is DataHub asset, embedded Predicate panel,
full review, certificate, remediation, and optional write-back.”

## Backup plan if live validation fails

Say this plainly:

“The live DataHub endpoint is unavailable in this recording, so I am switching
to the bundled DataHub-shaped fixture. This proves the SDK behavior and output
format, while the live validation checklist records exactly what must be
captured against a deployment.”

Backup commands:

```bash
predicate \
  "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)" \
  --policy examples/policies/enterprise_ai.yml \
  --datahub-file examples/data/datahub_graph.json \
  --explain

predicate \
  "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)" \
  --policy examples/policies/enterprise_ai.yml \
  --datahub-file examples/data/datahub_graph.json \
  --request-capability autonomous-agent-action

PYTHONPATH=src python3 scripts/evaluate_benchmark.py
```
