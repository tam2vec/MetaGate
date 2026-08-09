# Live DataHub Validation

The local seeded GraphQL test validates the adapter contract. A deployment
validation must still be run against the DataHub version used in the demo.

The validation run should prove one complete loop:

```text
Real DataHub entity -> metadata retrieval -> multi-hop traversal
-> certificate -> metadata change -> affected-asset rescan
-> capability change -> DataHub write-back
```

MetaGate's live evidence boundary is explicit:

| Evidence | Live source | If the deployment does not expose it |
| --- | --- | --- |
| Assertions | Dataset assertions plus `runEvents` and latest result | `unavailable`, never an automatic pass |
| Freshness | Freshness assertion run timestamp/result | `unavailable` unless a tested custom query supplies it |
| Usage | Dataset usage buckets | `unavailable`, never inferred from page views |
| Column lineage | `fineGrainedLineages` | `unavailable`, never inferred from table lineage |
| Incidents | Dataset incidents filtered to `ACTIVE`, including status | `unavailable`, never treated as zero |

The default GraphQL request is deliberately version-sensitive. If one field is
not supported, the adapter falls back to the core asset read and preserves the
failure reason in the evidence item. This makes a low-confidence result honest:
it means “the deployment did not let us observe enough,” not “the asset has no
metadata.”

## Read-only certification

For a repeatable check across multiple private assets, use the included
read-only validator. It never sends a mutation and never prints the token:

```bash
export DATAHUB_GRAPHQL_URL="https://datahub.example/api/graphql"
export DATAHUB_TOKEN="<read-only-token>"

PYTHONPATH=src python3 scripts/validate_private_datahub.py \
  --urn "urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.customer_lifetime_value,PROD)" \
  --urn "urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.revenue,PROD)"
```

For a strict deployment check, fail when a required DataHub surface is not
exposed instead of treating the run as complete:

```bash
PYTHONPATH=src python3 scripts/validate_private_datahub.py \
  --fail-on-unavailable \
  --urn "urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.customer_lifetime_value,PROD)"
```

The report includes the exact available and unavailable evidence plus the
score trace. This uses the same adapter as the CLI and Review API.

The output is the private-deployment proof artifact: the exact URN, decision,
readiness, confidence, evidence count, and reason for each asset.

```bash
export DATAHUB_GRAPHQL_URL=https://datahub.example/api/graphql
export DATAHUB_TOKEN="<read-only-token>"

metagate \
  "urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.revenue,PROD)" \
  --policy examples/policies/finance-production.yml \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --explain
```

If field names differ in the deployed DataHub version, provide a tested query
through `DATAHUB_ENTITY_QUERY` or the `GraphQLDataHubClient(query=...)` API.

The schema contract test can be run without a live server, and the live check
is opt-in locally but required in CI:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -q
export DATAHUB_GRAPHQL_URL="http://localhost:8080/api/graphql"
export METAGATE_LIVE_DATAHUB_URN="urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)"
PYTHONPATH=src python3 -m unittest tests.test_datahub_schema -v
```

The GitHub Actions job named `live DataHub schema contract` starts a clean
DataHub quickstart, ingests its sample metadata, and runs the same test against
`http://localhost:8080/api/graphql`. Mark that job as a required status check
in the repository branch-protection settings before calling the main branch
protected.

## Independent labels

`examples/benchmark/independent-label-template.csv` now contains 30 blank
review templates
covering allowed, blocked, and borderline judgments. The blank human fields
are intentional: MetaGate must not invent reviewer labels. A reviewer fills
`human_label` with `allowed`, `blocked`, or `borderline`, adds their role and
plain-language reason, then runs:

```bash
PYTHONPATH=src python3 scripts/evaluate_independent_labels.py \
  --labels examples/benchmark/independent-label-template.csv \
  --require-minimum
```

`borderline` is counted as a safety block. The report exposes the shortfall
until all 30 cases are actually reviewed; it is not presented as an accuracy
claim before that happens.

## Persistent review history and local overrides

MetaGate Review stores decisions, review notes, and override records in
`.context-gradient/review.sqlite3`. Restarting the service does not erase the
history. Inspect it through:

```text
/api/history?urn=<url-encoded-urn>&capability=autonomous-agent-action
/api/reviews?urn=<url-encoded-urn>&capability=autonomous-agent-action
/api/overrides?urn=<url-encoded-urn>&capability=autonomous-agent-action
```

Only `steward` and `admin` roles may submit an override, and every override
needs an actor and a reason. The local role header is a demo enforcement layer;
production deployments should map it to DataHub authentication and policy.

## Write-back validation

Use a non-production namespace first. The default path uses DataHub's supported
Python REST SDK rather than guessing a GraphQL mutation. It preserves existing
dataset properties, upserts one `metagate.ai_context_contract` property, polls
DataHub until that property is readable, and fails unless the read-back exactly
matches the contract that was written:

```bash
export DATAHUB_GRAPHQL_URL="http://localhost:8080/api/graphql"
export DATAHUB_GMS_URL="http://localhost:8080"

PYTHONPATH=src python3 scripts/writeback_datahub.py \
  "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)" \
  --policy examples/policies/enterprise_ai.yml \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --datahub-gms-url "$DATAHUB_GMS_URL" \
  --transport rest \
  --yes
```

The successful JSON receipt includes `transport: "datahub-rest-sdk"`,
`property_name: "metagate.ai_context_contract"`, and
`verified_readback: true`. Open the same dataset in DataHub and inspect its
Properties tab to see the written property. The command is intentionally
read/write: use a least-privilege token and a non-production dataset.

If your deployment does not expose the DatasetProperties REST aspect, use the
deployment-specific GraphQL path below. MetaGate still requires both a
mutation document and a read-back query:

```bash
PYTHONPATH=src python3 scripts/writeback_datahub.py \
  "urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.customer_lifetime_value,PROD)" \
  --policy examples/policies/finance-production.yml \
  --mutation-file examples/datahub-preflight-action/writeback-mutation.example.graphql \
  --verify-query-file examples/datahub-preflight-action/verify-contract.example.graphql \
  --yes
```

The example mutation is a template, not a universal promise: replace it with
the mutation supported by your DataHub version. The command will not report
success unless the read-back query returns a value. Use a separate
least-privilege token for write-back and keep evaluation tokens read-only.

## Evidence to capture

- DataHub version and GraphQL schema revision
- Certificate before a metadata change
- Metadata event or ingestion record
- Certificate after the change
- Readiness Diff and newly blocked/unlocked capabilities
- Asset-level write-back result
- Cache hit/miss status and scan duration

## Evidence capture template

| Evidence item | File or screenshot | Pass criteria | Notes |
| --- | --- | --- | --- |
| DataHub deployment version | `screenshots/01-datahub-version.png` | Version and environment are visible | Use a non-production namespace if possible. |
| Baseline asset page | `screenshots/02-asset-before.png` | Asset URN and current metadata are visible | Do not expose secrets or customer data. |
| Read-only certificate | `evidence/03-certificate-before.json` | Certificate includes score, capabilities, gaps, and timestamp | Run with a read-only token. |
| Blocked risky action | `evidence/04-blocked-action.json` | `allowed` is false for the risky capability | Prefer `autonomous-agent-action` for the demo. |
| Explainability report | `evidence/05-explainability.json` | Evidence, policy requirement, and decision path are present | This is the clearest judging artifact. |
| Metadata repair event | `screenshots/06-datahub-change.png` | DataHub shows the owner, assertion, glossary, or lineage repair | Keep the same asset URN. |
| Recomputed certificate | `evidence/07-certificate-after.json` | Timestamp changes and at least one gap/capability changes | Do not manually edit output. |
| Readiness diff | `evidence/08-readiness-diff.json` | Before/after capability movement is visible | Use for the demo close. |
| Write-back result | `screenshots/09-writeback.png` | Certificate or remediation task appears in DataHub | Only if deployment mutations are configured. |
| Benchmark result | `screenshots/10-benchmark.png` | 30 curated conformance checks pass with no unexpected allows or blocks | Say curated, not production. |

## Validation checklist

- [ ] Confirm the DataHub endpoint and token are for the intended demo environment.
- [ ] Use a read-only token for the baseline certification.
- [ ] Capture the baseline certificate before changing metadata.
- [ ] Capture one blocked risky capability.
- [ ] Capture the explainability report.
- [ ] Make exactly one visible metadata repair.
- [ ] Re-run certification on the same asset URN.
- [ ] Capture the readiness diff.
- [ ] Enable write-back only after the read-only loop works.
- [ ] Redact tokens, private URLs, and customer metadata before submission.

## Three-minute demo

1. An agent requests a risky action.
2. MetaGate blocks it.
3. The evidence-policy-decision report explains why.
4. Metadata is repaired inside DataHub.
5. The scanner recomputes affected assets.
6. The readiness diff shows the capability unlocked.
7. The updated context contract permits the action.
8. End on the public SDK and focused upstream contribution.
