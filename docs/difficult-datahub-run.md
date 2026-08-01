# Difficult DataHub Run

Use this fixture when you want a harder test than the happy-path sample data.

It simulates a high-risk finance dataset with:

- missing owner
- incomplete glossary
- incomplete column lineage
- contradictory assertions
- open incidents
- stale freshness
- weak upstream metadata
- downstream executive dashboard impact

Run:

```bash
PYTHONPATH=src python3 -m predicate.cli \
  "urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.customer_lifetime_value,PROD)" \
  --policy examples/policies/finance-production.yml \
  --datahub-file examples/data/difficult_datahub_graph.json \
  --request-capability autonomous-agent-action
```

Then run an explainability report:

```bash
PYTHONPATH=src python3 -m predicate.cli \
  "urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.customer_lifetime_value,PROD)" \
  --policy examples/policies/finance-production.yml \
  --datahub-file examples/data/difficult_datahub_graph.json \
  --explain
```

Expected story:

> Predicate blocks autonomous action because the asset is finance-critical,
> has unresolved quality and incident risk, and its lineage/ownership evidence
> is not strong enough for high-impact AI action.
