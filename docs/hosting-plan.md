# Hosted Demo Plan

The repository includes a screenshot-safe static review page and a live local
review server.

## Current demo surfaces

| Surface | Path | Use |
| --- | --- | --- |
| Static visual proof | `examples/outputs/predicate-demo-app.html` | Works offline and is safe for screenshots |
| Public static demo | `public-demo/index.html` | One-file deploy target for static hosting |
| Live local review app | `scripts/serve_review.py` | Browser loads decisions from `/api/runs` |
| Private review API container | `Dockerfile` | Runs the same review API behind a private network |
| DataHub embed prototype | `examples/datahub-embed/` | Shows how the panel mounts beside a DataHub asset |
| Browser extension prototype | `examples/browser-extension/` | Auto-runs Predicate on local DataHub asset pages |

## Public hosting requirement

A public hosted link should use the static visual proof page unless the host can
securely reach a DataHub deployment. Do not expose private DataHub URLs or
tokens in client-side JavaScript.

Safe public demo:

- hosted static Predicate Review page
- recorded sanitized demo decisions
- no customer data
- no DataHub token

Unsafe public demo:

- browser calling a private DataHub GraphQL endpoint directly
- checked-in bearer tokens
- live write-back enabled from public UI

## Private API Deployment

Build and run the review API container when the deployment environment can
securely reach DataHub:

```bash
docker build -t predicate-review .

docker run --rm -p 8765:8765 \
  -e DATAHUB_GRAPHQL_URL="http://host.docker.internal:8080/api/graphql" \
  predicate-review
```

Use this only for private demo networks or non-sensitive demo DataHub instances.
Do not expose a private DataHub token from a public static page.

## Judge-facing wording

Use:

> The hosted page is a sanitized visual demo. The local live review server shows
> the same UI backed by Predicate API calls against DataHub.

Avoid:

> The hosted page is connected to our private DataHub deployment.
