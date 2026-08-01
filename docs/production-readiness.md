# Production Readiness

Predicate is still a hackathon MVP, but these controls move it toward a real
private deployment.

## Runtime Controls

- `predicate` installed CLI for evaluations
- `predicate-review` installed API/review server
- `/healthz` process/config health endpoint
- `/readyz` decision-readiness endpoint
- Docker `HEALTHCHECK`
- Render health check configured against `/healthz`
- startup validation for policy path and data source
- `--no-recorded-fallback` for fail-closed private deployments
- configurable browser origin with `PREDICATE_CORS_ORIGIN`

## Safe Defaults

- read-only evaluation by default
- write-back requires deployment-provided mutation documents
- DataHub token stays server-side
- public demo uses sanitized fixture data
- private deployment can disable recorded fallback

## Required Private Deployment Environment

```bash
export DATAHUB_GRAPHQL_URL="https://datahub.example.com/api/graphql"
export DATAHUB_TOKEN="<private-token-if-required>"
export PREDICATE_CORS_ORIGIN="https://predicate-ui.example.com"

predicate-review \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --policy examples/policies/enterprise_ai.yml \
  --no-recorded-fallback \
  --cors-origin "$PREDICATE_CORS_ORIGIN"
```

## Production Checklist

Before claiming production deployment:

- [ ] DataHub token provided through secret manager
- [ ] API deployed inside private network
- [ ] `/healthz` monitored
- [ ] `/readyz` monitored
- [ ] recorded fallback disabled
- [ ] browser access restricted with `PREDICATE_CORS_ORIGIN`
- [ ] write-back mutations tested in non-production namespace
- [ ] RBAC/override roles mapped to DataHub policies
- [ ] audit logs retained
- [ ] external labels expanded beyond demo set
- [ ] one private DataHub dataset family validated end to end

## Honest Claim

Use:

> Predicate includes production-oriented runtime controls: health checks,
> startup validation, fail-closed mode, Docker healthcheck, server-side DataHub
> token handling, restricted browser access, and gated write-back.

Avoid:

> Predicate is production-ready for every DataHub deployment.
