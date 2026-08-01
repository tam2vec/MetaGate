# Live Predicate Review App

The static HTML proof page is useful for screenshots. The live review app is
better for demos because the browser loads decisions from a local Predicate API.

## Start it against local DataHub

Make sure local DataHub is running, then run:

```bash
export DATAHUB_GRAPHQL_URL="http://localhost:8080/api/graphql"

predicate-review \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --policy examples/policies/enterprise_ai.yml
```

Open:

```text
http://127.0.0.1:8765/review
```

The page will show:

- DataHub-style embedded Predicate panel
- live `/api/runs` data
- allowed and blocked outcomes
- readiness and confidence
- failed predicate terms
- full evidence review

## Evaluate one asset through the API

```text
http://127.0.0.1:8765/api/evaluate?urn=urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)&capability=autonomous-agent-action
```

## Use fixture mode if DataHub is unavailable

```bash
predicate-review \
  --datahub-file examples/data/datahub_graph.json \
  --policy examples/policies/enterprise_ai.yml \
  --urn "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)"
```

## What to say in the demo

> The HTML file is the screenshot-safe fallback. The local review server is the
> live version: the browser asks Predicate for decisions through `/api/runs`,
> and Predicate evaluates DataHub metadata through GraphQL.
