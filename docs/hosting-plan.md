# Hosted Demo Plan

The repository includes a screenshot-safe static review page and a live local
review server.

## Current demo surfaces

| Surface | Path | Use |
| --- | --- | --- |
| Static visual proof | `examples/outputs/metagate-demo-app.html` | Works offline and is safe for screenshots |
| Public static demo | `public-demo/index.html` | One-file deploy target for static hosting |
| Public API-backed demo | `https://leafy-maamoul-4acf4b.netlify.app/?api=https://metagate-ixz0.onrender.com` | Hosted page calling Render API; source is labelled fixture or live DataHub |
| Live local review app | `metagate-review` | Browser loads decisions from `/api/runs` |
| Private review API container | `Dockerfile` | Runs the same review API behind a private network |
| DataHub embed prototype | `examples/datahub-embed/` | Shows how the panel mounts beside a DataHub asset |
| Browser extension prototype | `examples/browser-extension/` | Auto-runs MetaGate on local DataHub asset pages |

## Public hosting requirement

A public hosted link must use the API-backed page, and the API must securely
reach a DataHub deployment before it is called live. Do not expose private
DataHub URLs or tokens in client-side JavaScript.

Safe public fallback:

- hosted static MetaGate Review page
- recorded sanitized demo decisions
- optional public Render API using sanitized fixture data
- no customer data
- no DataHub token

Live public demo requirements:

- Render `METAGATE_DEMO_MODE=live`
- Render `DATAHUB_GRAPHQL_URL` points to a reachable DataHub GraphQL endpoint
- Render-only `DATAHUB_TOKEN` with read-only permission
- `/api/status` reports `live_datahub: true` and `fixture_fallback_blocked: true`

Unsafe public demo:

- browser calling a private DataHub GraphQL endpoint directly
- checked-in bearer tokens
- live write-back enabled from public UI

## Private API Deployment

Build and run the review API container when the deployment environment can
securely reach DataHub:

```bash
docker build -t metagate-review .

docker run --rm -p 8765:8765 \
  -e DATAHUB_GRAPHQL_URL="http://host.docker.internal:8080/api/graphql" \
  -e DATAHUB_TOKEN="<optional-private-token>" \
  -e METAGATE_CORS_ORIGIN="https://metagate-ui.example.com" \
  metagate-review
```

Health endpoints:

- `/healthz`: process and configuration health
- `/readyz`: checks whether the API can return at least one decision

For private deployments, start with `--no-recorded-fallback` so the API fails
closed instead of returning recorded demo data when DataHub evaluation fails.
Set `METAGATE_CORS_ORIGIN` to the exact UI URL that is allowed to call the API.

Use this only for private demo networks or non-sensitive demo DataHub instances.
Do not expose a private DataHub token from a public static page.

## Judge-facing wording

Use:

> MetaGate’s hosted review page is API-backed and source-labelled. In live
> mode the server reads DataHub GraphQL with fixture fallback disabled; in safe
> fallback mode it clearly says that the data is a fixture.

Avoid:

> The hosted page is connected to our private DataHub deployment.
