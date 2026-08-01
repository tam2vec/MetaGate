# Live DataHub Validation

The local seeded GraphQL test validates the adapter contract. A deployment
validation must still be run against the DataHub version used in the demo.

The validation run should prove one complete loop:

```text
Real DataHub entity -> metadata retrieval -> multi-hop traversal
-> certificate -> metadata change -> affected-asset rescan
-> capability change -> DataHub write-back
```

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

The output is the private-deployment proof artifact: the exact URN, decision,
readiness, confidence, evidence count, and reason for each asset.

```bash
export DATAHUB_GRAPHQL_URL=https://datahub.example/api/graphql
export DATAHUB_TOKEN="<read-only-token>"

predicate \
  "urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.revenue,PROD)" \
  --policy examples/policies/finance-production.yml \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --explain
```

If field names differ in the deployed DataHub version, provide a tested query
through `DATAHUB_ENTITY_QUERY` or the `GraphQLDataHubClient(query=...)` API.

## Write-back validation

Use a non-production namespace first. The repository now includes a command that
requires both a mutation document and a read-back query:

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
2. Predicate blocks it.
3. The evidence-policy-decision report explains why.
4. Metadata is repaired inside DataHub.
5. The scanner recomputes affected assets.
6. The readiness diff shows the capability unlocked.
7. The updated context contract permits the action.
8. End on the public SDK and focused upstream contribution.
