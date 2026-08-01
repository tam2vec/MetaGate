# Three-Minute Demo Script

This script is written for a judge who has never seen Predicate.

## Setup

Open these before recording:

- DataHub asset page for `fct_users_created`
- Predicate public page or local review app
- Terminal in the Predicate repo
- README on GitHub

Keep the language honest:

> The public page is a sanitized demo. The real proof path is local/private
> DataHub GraphQL plus the Predicate CLI/API.

## 0:00-0:20 - The Problem

Screen: DataHub asset page.

Say:

> Companies spent years adding metadata for people: owners, glossary terms,
> lineage, quality checks, freshness, incidents, and policies. Now AI agents are
> being asked to act on that same data. The missing question is simple: is the
> metadata good enough to let the agent act?

## 0:20-0:45 - The Product

Screen: Predicate README, then Predicate Review.

Say:

> Predicate is an AI admission controller for DataHub. It turns metadata into a
> deterministic action check. No metadata proof, no AI action.

Show this idea:

```json
{
  "action": "autonomous-agent-action",
  "predicate": "ownership.present && lineage.present && assertions.present && incidents.open == 0",
  "result": false,
  "failed_terms": ["assertions.present"],
  "decision": "blocked"
}
```

## 0:45-1:15 - Live DataHub Decision

Screen: terminal.

Run:

```bash
export DATAHUB_GRAPHQL_URL="http://localhost:8080/api/graphql"

predicate \
  "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)" \
  --policy examples/policies/enterprise_ai.yml \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --request-capability autonomous-agent-action
```

Say:

> This is reading the local DataHub GraphQL endpoint. Predicate blocks
> autonomous action on this asset because assertions are missing and the score
> and confidence are below policy thresholds.

Point to:

- `allowed: false`
- same DataHub URN
- missing assertions
- readiness/confidence thresholds

## 1:15-1:45 - Same Policy, Different Asset

Screen: terminal.

Run:

```bash
predicate \
  "urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)" \
  --policy examples/policies/enterprise_ai.yml \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --request-capability autonomous-agent-action
```

Say:

> Predicate is not just a blocker. Under the same policy, this asset is allowed
> because the required evidence is present. The point is controlled action, not
> blanket denial.

## 1:45-2:15 - Human Review Experience

Screen: Predicate Review page.

Say:

> The terminal output is for automation. The product experience is this review
> surface: the basic decision appears beside the DataHub asset, and the full
> review explains the failed terms, remediation plan, capability matrix, trust
> timeline, and write-back queue.

Click:

- blocked `fct_users_created`
- remediation drawer
- capability matrix
- trust timeline

Say:

> This is where Predicate becomes operational. It does not say """add metadata."""
> It says which checks to add, why they matter, and what should unlock after the
> repair.

## 2:15-2:35 - Stress Case

Screen: Predicate Review finance asset or difficult run docs.

Say:

> For a harder case, Predicate includes a finance-critical asset. It blocks
> autonomous action because glossary terms are incomplete, column lineage is
> incomplete, assertions conflict, freshness is stale, and finance policy has
> stricter thresholds.

Point to:

- `customer_lifetime_value`
- finance glossary terms
- column lineage repairs
- stale freshness
- stricter score threshold

## 2:35-2:50 - Engineering Proof

Screen: terminal.

Run:

```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 scripts/evaluate_benchmark.py
```

Say:

> The repository has automated tests and a 30-case curated conformance suite
> covering ready, missing, stale, incomplete, and contradictory metadata states.
> This validates policy behavior; it is not a production accuracy claim.

## 2:50-3:00 - Close

Screen: README proof links.

Say:

> Predicate gives AI agents a metadata-backed permission layer. The output is
> simple: allowed or blocked. The proof is explicit: which predicate terms passed,
> which failed, who needs to repair them, and when the action can be rerun.

## If Something Breaks

Use this backup line:

> The live DataHub endpoint is unavailable in this recording, so I am switching
> to the bundled DataHub-shaped fixture. That proves the Predicate engine and
> output contract; the local DataHub runbook shows the live GraphQL path.

Backup command:

```bash
predicate \
  "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)" \
  --policy examples/policies/enterprise_ai.yml \
  --datahub-file examples/data/datahub_graph.json \
  --request-capability autonomous-agent-action \
  --explain
```
