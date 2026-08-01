# Write-back Safety

Predicate is read-only by default.

The engine can generate a Predicate Certificate and remediation task payload,
but it does not write to live DataHub unless deployment-specific mutation
documents are explicitly configured.

## Why write-back is gated

DataHub deployments differ by version, enabled features, custom aspects, and
permissions. A generic mutation that works in one environment may fail or write
the wrong shape in another.

Predicate therefore separates:

- evaluation: always available
- payload generation: always available
- live write-back: enabled only by the deployment owner

## Required environment variables

```bash
export DATAHUB_GRAPHQL_URL="http://localhost:8080/api/graphql"
export DATAHUB_TOKEN="<token-if-required>"
export DATAHUB_CERTIFICATE_MUTATION="$(cat path/to/certificate-mutation.graphql)"
export DATAHUB_TASK_MUTATION="$(cat path/to/task-mutation.graphql)"
```

`DATAHUB_CERTIFICATE_MUTATION` and `DATAHUB_TASK_MUTATION` are intentionally not
bundled as universal defaults because the correct mutation depends on the
target DataHub version and custom aspect setup.

## Safe demo sequence

1. Run read-only evaluation.
2. Save the JSON decision and Predicate Certificate.
3. Inspect the generated write-back payload.
4. Configure mutation documents only in a non-production namespace.
5. Run write-back.
6. Reopen the same DataHub asset URN and verify the certificate or task appears.

Receipt-only demo command:

```bash
predicate \
  "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)" \
  --policy examples/policies/enterprise_ai.yml \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --writeback-file examples/outputs/writeback-receipt.json
```

This writes a local receipt without requiring a DataHub mutation. Treat it as
proof of the payload contract, not proof of a live DataHub UI mutation.

## Demo artifacts

- `examples/outputs/writeback-payload.json`: representative certificate body.
- `examples/outputs/writeback-receipt.json`: safe receipt for the local demo.
- `examples/outputs/writeback-proof.json`: explains why no mutation is sent by
  default.

## Judge-facing wording

Use:

> Predicate is read-only by default. It can generate certificate and remediation
> task payloads, and live DataHub write-back is enabled only when the deployment
> owner provides the mutation documents for their DataHub version.

Avoid:

> Predicate writes certificates to every DataHub instance out of the box.
