# Independent Evaluation

The repository includes a 30-case curated benchmark. A stronger result comes
from a held-out set created by a mentor, teammate, or reviewer who did not
inspect the scoring rules.

## Protocol

1. Give the reviewer the schema and policy contract, not the implementation.
2. Ask for 10 unseen scenarios across ready, missing, stale, incomplete, and contradictory states.
3. Store the labeled cases separately from `cases.json`.
4. Run the unchanged evaluator:

```bash
PYTHONPATH=src python3 scripts/evaluate_benchmark.py \
  --cases /path/to/independent-cases.json \
  --label "independent held-out set"
```

5. Report the held-out cases, positive definition, conformance pass rate,
   unexpected allows, and unexpected blocks separately from the curated checks.

Do not call the result production accuracy or universal precision. The point is
to show that an evaluator who did not author the rules can still produce a
reproducible, labeled test set.
