# Upstream DataHub PR Template

## Title

Add AI metadata readiness certification example

## Summary

This PR proposes a DataHub example for certifying whether a metadata asset is
ready for AI-assisted actions. The example uses DataHub metadata evidence to
produce a Predicate Certificate, explain allowed and blocked capabilities, and
show how metadata repairs change agent permissions over time.

The contribution is intentionally example-first. It does not require a core
DataHub schema change and can later evolve into a custom aspect, Action, or
plugin if the community wants a deeper integration.

## Motivation

AI agents need more than metadata access. They need an admission control layer
that determines whether metadata is complete, fresh, and governed enough for a
specific action. Predicate demonstrates this using DataHub evidence such
as ownership, glossary terms, lineage, assertions, incidents, freshness, usage,
and policy tags.

## Proposed files

- `metadata-ai-readiness/README.md`
- `metadata-ai-readiness/architecture.md`
- `metadata-ai-readiness/evidence-model.md`
- `metadata-ai-readiness/examples/policies/enterprise_ai.yml`
- `metadata-ai-readiness/examples/datahub_graph.json`
- `metadata-ai-readiness/datahub-ai-readiness-skill/README.md`
- `metadata-ai-readiness/datahub-ai-readiness-skill/plugin.json`

## Validation

- Local SDK tests pass.
- Curated 30-case conformance suite passes with no unexpected allows or blocks.
- Live deployment validation should be run against the target DataHub version
  before promoting the example as production-ready.

## Screenshots or artifacts

- Architecture diagram.
- Predicate Certificate example.
- Explainability report.
- Readiness diff before and after metadata repair.

## Compatibility

This is an example contribution and does not change DataHub core behavior. Live
write-back is deployment-specific and should use the mutation documents
supported by the target DataHub version.
