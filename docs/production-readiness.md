# Production Readiness

MetaGate is still a hackathon MVP, but these controls move it toward a real
private deployment.

## Runtime Controls

- `metagate` installed CLI for evaluations
- `metagate-review` installed API/review server
- `/healthz` process/config health endpoint
- `/readyz` decision-readiness endpoint
- `/api/status` machine-readable product, mode, and data-source status
- Docker `HEALTHCHECK`
- Render health check configured against `/healthz`
- startup validation for policy path and data source
- `--no-recorded-fallback` for fail-closed private deployments
- configurable browser origin with `METAGATE_CORS_ORIGIN`

## Safe Defaults

- read-only evaluation by default
- live write-back requires the explicit `--enable-writeback` flag
- write-back requires deployment-provided mutation documents
- DataHub token stays server-side
- public demo uses sanitized fixture data
- private deployment can disable recorded fallback

## Required Private Deployment Environment

```bash
export DATAHUB_GRAPHQL_URL="https://datahub.example.com/api/graphql"
export DATAHUB_TOKEN="<private-token-if-required>"
export METAGATE_CORS_ORIGIN="https://metagate-ui.example.com"

metagate-review \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --policy examples/policies/enterprise_ai.yml \
  --no-recorded-fallback \
  --cors-origin "$METAGATE_CORS_ORIGIN"
```

## Production Checklist

Before claiming production deployment:

- [ ] DataHub token provided through secret manager
- [ ] API deployed inside private network
- [ ] `/healthz` monitored
- [ ] `/readyz` monitored
- [ ] recorded fallback disabled
- [ ] browser access restricted with `METAGATE_CORS_ORIGIN`
- [ ] write-back mutations tested in non-production namespace
- [ ] RBAC/override roles mapped to DataHub policies
- [ ] audit logs retained
- [ ] external labels expanded beyond demo set
- [ ] one private DataHub dataset family validated end to end

For a hosted demo, open `/api/status` to verify whether the page is using a
sanitized fixture API or a live DataHub GraphQL API. The page should never imply
that a fixture is a private DataHub deployment.

## Honest Claim

Use:

> MetaGate includes production-oriented runtime controls: health checks,
> startup validation, fail-closed mode, Docker healthcheck, server-side DataHub
> token handling, restricted browser access, and gated write-back.

Avoid:

> MetaGate is production-ready for every DataHub deployment.
