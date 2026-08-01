# Good First Issues

These are small, useful contributions for new Predicate contributors.

## Documentation

- Add a screenshot of the browser extension running on a local DataHub asset page.
- Add a short troubleshooting entry for a DataHub GraphQL schema mismatch.
- Add a one-page guide for running Predicate against a DataHub Cloud sandbox.

## Policies

- Add a healthcare policy profile with HIPAA-style evidence requirements.
- Add a finance policy profile for schema-change approval.
- Add a low-risk discovery policy for read-only AI assistant use.

## Benchmarks

- Add one independently labeled benchmark row using
  `examples/benchmark/independent-label-template.csv`.
- Add a fixture case where lineage is present but downstream owners are missing.
- Add a fixture case where glossary terms conflict with the asset description.

## UI

- Add a copy button for the action predicate JSON.
- Add a filter for allowed vs blocked assets in the public review page.
- Add a compact view for narrow laptop screens.

## Integrations

- Add a sample DataHub mutation document for a non-production custom property
  write-back.
- Package the browser extension as a zipped artifact for manual Chrome install.
- Add a Docker Compose service for the Predicate review API.
