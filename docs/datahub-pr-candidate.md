# DataHub PR Candidate

**Predicate helps teams know when AI is allowed to act.**

This repository is prepared as a documentation/example contribution for DataHub:

## Proposed contribution

Add an `metadata-ai-readiness` example showing how to certify DataHub assets for AI use.

## Files to upstream

- `README.md`
- `docs/architecture.md`
- `docs/evidence-model.md`
- `examples/policies/enterprise_ai.yml`
- `examples/data/datahub_graph.json`
- `examples/datahub-ai-readiness-skill/README.md`
- `examples/datahub-ai-readiness-skill/plugin.json`
- `src/context_gradient/datahub/adapter.py`

## Why this fits DataHub

The contribution demonstrates graph-aware metadata quality without requiring a core DataHub change. It can later be promoted to a custom aspect or an Actions plugin.

## Live implementation notes

Use DataHub GraphQL/OpenAPI to fetch:

- ownership
- glossary terms
- upstream and downstream lineage
- assertions
- incidents
- freshness
- usage statistics
- custom policy tags or aspects

Write back through one of:

- a custom AI readiness aspect
- DataHub assertions
- DataHub tasks
- incidents for remediation workflows
