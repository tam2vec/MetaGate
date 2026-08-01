# Public Demo Runbook

**Predicate helps teams know when AI is allowed to act.**

This runbook is the shortest path to a reproducible Predicate demo. The public
page is either a static visual demo or a Render API-backed fixture demo; the
real DataHub proof runs locally or inside a private DataHub deployment.

## Local proof

```bash
python -m pip install -e ".[dev]"
PYTHONPATH=src python -m unittest discover -s tests -v
predicate \
  "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)" \
  --policy examples/policies/enterprise_ai.yml \
  --datahub-file examples/data/datahub_graph.json
```

The demo shows the certificate, allowed capabilities, blocked capabilities,
evidence gaps, recommendations, and context contract.

Say precisely: “Our curated 30-case conformance suite passes with no unexpected
allows or blocks. That validates the policy behavior in this repository; it is
not a production accuracy claim.”

## Live DataHub proof

Set `DATAHUB_GRAPHQL_URL` and `DATAHUB_TOKEN`, then run the same command with
`--datahub-url`. Use a read-only token for certification. Add the exact
deployment-supported mutation documents in `DATAHUB_CERTIFICATE_MUTATION` and
`DATAHUB_TASK_MUTATION` only after testing them in a non-production namespace.

## Submission proof

Capture the CLI output, the generated certificate, one changed metadata event,
and the resulting readiness diff. Include the repository URL, CI run URL, and
DataHub version in the submission. Do not describe a local fixture as a live
DataHub deployment.
