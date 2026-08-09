# Private Deployment Adapter

MetaGate should be deployed beside a private DataHub instance, not as a public
service connected to private metadata.

## Default Data Access

MetaGate consumes metadata by default:

- asset URN
- schema and column descriptions
- ownership
- glossary terms
- tags and domain
- lineage and column lineage
- assertions and assertion results
- freshness signals
- incidents
- usage and downstream consumers
- policy profile
- previous MetaGate decision records

MetaGate does not need raw table rows for the default admission decision.

Optional sampled profiles can be added by a deployment owner, but they should be
treated as sensitive and governed by the same access rules as DataHub metadata.

## Private Deployment Shape

```text
DataHub UI
  -> Request AI Readiness
  -> MetaGate API inside private network
  -> DataHub GraphQL metadata read
  -> MetaGate policy evaluation
  -> Context Contract
  -> optional DataHub write-back
```

## Finance Stress Case

The demo finance asset simulates a clean-looking schema that should still be
blocked:

- missing or weak owner
- incomplete glossary
- incomplete column lineage
- contradictory metric definitions
- stale freshness
- open incidents
- downstream executive dashboard impact

The point is:

> A schema can look clean while the metadata is not decision-ready.

Run:

```bash
metagate \
  "urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.customer_lifetime_value,PROD)" \
  --policy examples/policies/finance-production.yml \
  --datahub-file examples/data/difficult_datahub_graph.json \
  --request-capability autonomous-agent-action
```

When you have access to a real private DataHub, replace the fixture with the
read-only validator in [Live DataHub Validation](live-datahub-validation.md).
That is the strongest test available without exposing an organization’s
metadata or credentials in this repository.
