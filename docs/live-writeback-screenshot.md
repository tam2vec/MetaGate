# Live Write-back Screenshot

Predicate cannot safely ship a universal DataHub write-back mutation because
DataHub deployments differ by version, custom aspects, permissions, and enabled
features.

For the hackathon demo, capture one of these proof paths.

## Preferred proof

1. Configure a non-production DataHub deployment with a tested mutation for a
   Predicate Certificate custom aspect or equivalent metadata field.
2. Set `DATAHUB_CERTIFICATE_MUTATION`.
3. Run Predicate on the same asset URN.
4. Reopen the DataHub asset page.
5. Capture a screenshot showing the Predicate Certificate, custom property,
   assertion, tag, or remediation task.

## Safe fallback proof

If live mutation support is not available, show:

- `examples/outputs/writeback-payload.json`
- `examples/outputs/writeback-receipt.json`
- `docs/writeback-safety.md`
- the Predicate Review UI showing the certificate and remediation path

Generate a fresh local receipt:

```bash
predicate \
  "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)" \
  --policy examples/policies/enterprise_ai.yml \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --writeback-file examples/outputs/writeback-receipt.json
```

Then capture:

1. terminal command with the same URN
2. `examples/outputs/writeback-receipt.json`
3. Predicate Review write-back queue
4. DataHub asset page for the same URN

This proves the generated write-back contract even when live mutation is not
enabled.

## Screenshot checklist

The screenshot should include:

- DataHub URL or local host
- the same asset URN used in the terminal/API run
- visible Predicate result or metadata field
- timestamp if DataHub displays one
- no private tokens or customer data

## Judge-facing wording

Use:

> Predicate is read-only by default. This receipt shows the certificate and task
> payload that would be written. Live write-back requires the deployment's
> approved mutation document.
