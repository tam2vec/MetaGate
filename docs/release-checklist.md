# v0.1.0 Release Checklist

## Pre-release

- [ ] Confirm `pyproject.toml` version is `0.1.0`.
- [ ] Confirm `CHANGELOG.md` has a `0.1.0` section.
- [ ] Run `pytest`.
- [ ] Run `PYTHONPATH=src python3 scripts/evaluate_benchmark.py`.
- [ ] Review README links and images on GitHub.
- [ ] Confirm no credentials or customer metadata are present.
- [ ] Tag the release candidate as `v0.1.0`.

## Release notes draft

Title: `Predicate v0.1.0`

Predicate v0.1.0 is the first public release of an AI-readiness
certification SDK and DataHub integration reference.

Highlights:

- Generates Predicate Certificates from DataHub-style metadata evidence.
- Certifies capabilities such as explain, summarize, query, and modify.
- Blocks risky actions when ownership, glossary, lineage, freshness,
  assertions, incidents, usage, or policy evidence is missing or stale.
- Produces context contracts for agent-facing permissions.
- Emits explainability reports, readiness diffs, audit entries, and
  representative DataHub write-back payloads.
- Includes configurable YAML policy profiles.
- Includes an installable CLI and Python SDK.
- Includes a DataHub Skill/plugin reference in `examples/datahub-ai-readiness-skill`.
- Includes a 30-case curated benchmark across ready, missing, stale,
  incomplete, and contradictory metadata states.

Validation:

- Curated conformance checks: 30/30 passing.
- Unexpected allows: 0 in the curated checks.
- Unexpected blocks: 0 in the curated checks.
- Production accuracy claims are intentionally excluded pending independent
  real-world validation.

Notes:

- Live DataHub write-back is deployment-specific and requires GraphQL mutation
  documents configured through environment variables.
- Use `docs/live-datahub-validation.md` before presenting deployment evidence.

## Suggested GitHub commands

```bash
git tag -a v0.1.0 -m "Predicate v0.1.0"
git push origin v0.1.0
```
