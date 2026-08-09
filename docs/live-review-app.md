# Live MetaGate Review App

The static HTML proof page is useful for screenshots. The live review app is
better for demos because the browser loads decisions from a local MetaGate API.

## Start it against local DataHub

Make sure local DataHub is running, then run:

```bash
export DATAHUB_GRAPHQL_URL="http://localhost:8080/api/graphql"

metagate-review \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --policy examples/policies/enterprise_ai.yml
```

Open:

```text
http://127.0.0.1:8765/review
```

The page will show:

- DataHub-style embedded MetaGate panel
- live `/api/runs` data
- allowed and blocked outcomes
- readiness and confidence
- failed metagate terms
- full evidence review

Local human-review decisions are persisted by the API in
`.context-gradient/review-notes.jsonl`. `GET /api/reviews` returns saved
records for one asset and capability, and `POST /api/reviews` appends a new
record. A hosted static page has no private persistence service, so it uses
browser storage until a deployment-owned database endpoint is provided.

Health checks:

```text
http://127.0.0.1:8765/healthz
http://127.0.0.1:8765/readyz
```

## Evaluate one asset through the API

```text
http://127.0.0.1:8765/api/evaluate?urn=urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)&capability=autonomous-agent-action
```

## Use fixture mode if DataHub is unavailable

```bash
metagate-review \
  --datahub-file examples/data/datahub_graph.json \
  --policy examples/policies/enterprise_ai.yml \
  --urn "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)"
```

## Fail closed in private deployments

Use `--no-recorded-fallback` when the API is connected to a private DataHub
deployment:

```bash
metagate-review \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --policy examples/policies/enterprise_ai.yml \
  --no-recorded-fallback
```

That prevents the server from returning recorded demo data if live DataHub
evaluation fails.

For private deployments, restrict which browser UI can call the API:

```bash
export METAGATE_CORS_ORIGIN="https://metagate-ui.example.com"

metagate-review \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --policy examples/policies/enterprise_ai.yml \
  --no-recorded-fallback \
  --cors-origin "$METAGATE_CORS_ORIGIN"
```

## What to say in the demo

> The HTML file is the screenshot-safe fallback. The local review server is the
> live version: the browser asks MetaGate for decisions through `/api/runs`,
> and MetaGate evaluates DataHub metadata through GraphQL.
