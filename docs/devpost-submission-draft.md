# Devpost Submission Draft

## Project name

Predicate

## Short description

Predicate is an AI admission controller for DataHub: it turns metadata evidence
into go/no-go decisions that decide which agent actions are safe.

## Long description

Enterprise metadata catalogs were built so people could understand data. AI
agents need something stricter: a deterministic way to know whether metadata is
complete, current, and governed enough for a specific action.

Predicate certifies DataHub assets for AI use. It reads evidence such as
ownership, glossary terms, lineage, assertions, incidents, freshness, usage, and
policy tags, then produces a Predicate Certificate. The certificate says which
capabilities are allowed, which are blocked, and why.

The core idea is simple: do not ask an AI agent to guess whether it can be
trusted. Put a policy-driven admission controller between the agent and the
metadata graph.

## Features

- Predicate Certificates for DataHub assets.
- Capability-level admission control for agent actions.
- Deterministic evidence-to-policy-to-decision explanations.
- Concrete remediation plans for missing assertions, stale freshness,
  incomplete lineage, ownership gaps, and policy threshold failures.
- YAML policy profiles for different risk levels.
- Readiness diffs that show how metadata repairs change certified capabilities.
- Context contracts that expose machine-readable permissions to agents.
- DataHub-style graph traversal through fixture, adapter, or live GraphQL mode.
- Browser extension prototype that auto-runs Predicate when a local DataHub asset
  page opens.
- Dockerized review API path for private demos.
- DataHub embed prototype showing the intended asset-page side panel.
- Representative write-back payloads for certificates and remediation tasks.
- Curated benchmark across ready, missing, stale, incomplete, and contradictory
  metadata states.
- Independent label scoring workflow for reviewer-labeled held-out cases.

## Technical architecture

Predicate has four layers:

1. DataHub evidence extraction collects ownership, glossary, lineage,
   assertions, incidents, freshness, usage, and policy metadata.
2. The readiness engine evaluates that evidence against a YAML policy profile.
3. The admission layer converts the certificate into allowed or blocked agent
   capabilities.
4. Reporting and integration layers emit Predicate Certificates, context
   contracts, explainability reports, readiness diffs, audit entries, and
   write-back payloads.

The MVP includes a Python SDK, CLI, local DataHub-shaped fixture client, live
GraphQL client, local API-backed review app, browser extension prototype,
Dockerfile, DataHub Skill/plugin reference, DataHub embed prototype, benchmark,
examples, and architecture documentation.

## Originality

Most metadata tooling focuses on discovery, documentation, or quality checks.
Predicate treats metadata as an AI control plane. Its contribution is the
Predicate Certificate: a reusable, deterministic contract that decides whether a
specific AI action should be allowed based on graph evidence and policy.

## Impact

Predicate helps teams adopt AI agents without giving them blanket access
to change production data systems. It creates a clear path from metadata quality
work to measurable AI readiness: repair the metadata, rerun certification, and
show exactly which capabilities changed.

## Installation

```bash
python -m pip install -e ".[dev]"
predicate \
  "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)" \
  --policy examples/policies/enterprise_ai.yml \
  --datahub-file examples/data/datahub_graph.json
```

For live DataHub mode:

```bash
export DATAHUB_GRAPHQL_URL="https://your-datahub.example/api/graphql"
export DATAHUB_TOKEN="<token>"

predicate \
  "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)" \
  --policy examples/policies/enterprise_ai.yml \
  --datahub-url "$DATAHUB_GRAPHQL_URL"
```

## Validation

The repository includes a curated suite of 30 policy conformance checks. The
current result is 30/30 checks passing, with no unexpected allows or blocks in
that suite. This is not presented as production accuracy. Real deployment
validation should follow
`docs/live-datahub-validation.md`.

Predicate was also run against a local DataHub quickstart seeded with sample
metadata. The same policy produced both allowed and blocked outcomes across
different DataHub assets. The public hosted page is a sanitized static demo of
the intended embedded experience; the local review server is the live
API-backed proof path.

The repository also includes an independent-label CSV template and scorer. That
workflow is ready for external reviewers, but independent agreement should only
be claimed after reviewers label held-out cases.

## Limitations

- The benchmark is curated and should be expanded with independent enterprise
  cases.
- Live write-back depends on the GraphQL mutations supported by the target
  DataHub deployment.
- The DataHub embed is a prototype contract and panel renderer, not a packaged
  production DataHub frontend plugin.
- The automatic DataHub page integration is a browser extension prototype, not a
  packaged production DataHub plugin.
- The public hosted demo is sanitized static proof, not a live DataHub
  deployment.
- The repository includes a local DataHub-shaped fixture for reproducible
  demos; fixture output should not be described as live deployment evidence.
- The MVP focuses on certification, admission control, local review, and
  integration reference behavior rather than a production hosted SaaS.
