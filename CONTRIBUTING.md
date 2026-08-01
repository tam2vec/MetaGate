# Contributing

Predicate is structured so the AI-readiness SDK can evolve independently from the DataHub integration.

## Local development

```bash
python -m pip install -e ".[dev]"
pytest
```

## Contribution standards

- Add tests for scoring, policy, DataHub extraction, and write-back behavior.
- Keep policy behavior deterministic.
- Treat live DataHub calls as adapters around the SDK models.
- Document every new evidence signal in `docs/evidence-model.md`.

## DataHub upstream candidate

The upstream-quality contribution path is a DataHub example integration rather than a core patch:

- `examples/datahub-ai-readiness-skill/README.md`
- policy-as-code examples
- GraphQL/OpenAPI extraction mapping
- write-back mapping for assertions, custom aspects, and tasks
