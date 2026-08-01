# Evaluation Benchmark

The bundled benchmark is intentionally curated and transparent. It contains
30 labeled policy scenarios across ready, missing, stale, incomplete, and
contradictory metadata states.

Run it with:

```bash
PYTHONPATH=src python3 scripts/evaluate_benchmark.py
```

The benchmark defines a positive as: **the asset satisfies the requested
capability policy**. The command reports cases, the conformance pass rate for
the curated checks, unexpected allows, and unexpected blocks.

Current result: Predicate passes all 30 curated policy conformance
checks across ready, missing, stale, incomplete, and contradictory metadata
states. The current run has 0 unexpected allows and 0 unexpected blocks.

| Category | Cases | Expected behavior |
| --- | ---: | --- |
| Ready | 6 | Allow the requested capability when required evidence is present. |
| Missing | 6 | Block when required evidence is absent. |
| Stale | 6 | Block when evidence exists but is out of date. |
| Incomplete | 6 | Block when evidence does not satisfy the full policy. |
| Contradictory | 6 | Block when metadata conflicts create unsafe ambiguity. |

| Metric | Current curated result |
| --- | ---: |
| Total cases | 30 |
| Curated conformance checks passed | 30 |
| Unexpected allows | 0 |
| Unexpected blocks | 0 |

This is useful engineering validation, but it is not production accuracy,
independent enterprise validation, or a universal precision claim. Expand
`examples/benchmark/cases.json` with labeled assets from a sanitized DataHub
export before making an enterprise quality claim. For an admission controller,
track unexpected allows separately: an unsafe allow is more serious than a
conservative block.
