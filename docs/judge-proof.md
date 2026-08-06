# Judge Proof

This page separates what Predicate already demonstrates from what remains
production work.

## One-command proof bundle

Run `./scripts/judge_proof.sh` from the repository root. It produces
`/tmp/predicate-release-proof.json` with the exact commit and the status of:

- the full repository test suite;
- the curated 30-case benchmark;
- the allowed explanation, blocked executive metric, blocked modification,
  and blocked restricted-SQL story;
- agreement between Predicate's Skill and MCP surfaces;
- the packaged browser extension;
- local DataHub and review-server prerequisites;
- the live schema-contract test when its environment variables are present.

The bundle also lists external proof still required. This is deliberate:
missing credentials, a private deployment, an upstream maintainer review, and
independent human labels cannot be honestly replaced by a local fixture.

## Demonstrated in this repository

| Claim | Evidence |
| --- | --- |
| Predicate can evaluate DataHub metadata for a specific AI action. | `src/context_gradient/datahub/adapter.py`, live GraphQL mode, and `examples/outputs/live-runs.json` |
| Predicate produces both allowed and blocked decisions. | `examples/outputs/allowed-action.json`, `examples/outputs/blocked-action.json`, and the visual review page |
| Decisions are explainable. | `examples/outputs/explainability-report.json`, `examples/outputs/action-predicate.json` |
| The same engine supports human UI and machine JSON. | `examples/outputs/predicate-demo-app.html`, CLI output, context contract JSON |
| A DataHub page can trigger Predicate automatically. | `examples/browser-extension/` reads the DataHub asset URN and calls `/api/evaluate`. |
| DataHub can remain the system of record. | `examples/datahub-embed/` panel prototype and `docs/why-predicate.md` |
| Write-back is designed safely. | `docs/writeback-safety.md`, `examples/outputs/writeback-receipt.json` |
| Policy behavior has regression coverage. | `tests/` and `scripts/evaluate_benchmark.py` |
| Harder metadata failures are modeled. | `examples/data/difficult_datahub_graph.json` and `docs/difficult-datahub-run.md` |

## Honest limitations

| Limitation | Current mitigation |
| --- | --- |
| The DataHub panel is not packaged as a production DataHub plugin. | `dist/Predicate-DataHub-extension.zip` is installable in Chrome; native DataHub frontend registration remains deployment-specific. |
| The automatic page integration is a browser extension prototype. | It proves the UX loop while avoiding assumptions about DataHub frontend packaging. |
| The public hosted page is fixture-backed unless a reachable DataHub is deliberately configured. | The page labels its source; the local review server loads the same UI through `/api/runs` and can query DataHub GraphQL. |
| The benchmark is curated by the project. | The README and benchmark docs avoid production accuracy claims and provide a held-out evaluation template. |
| Live write-back depends on DataHub version and custom mutation support. | Predicate is read-only by default and requires an approved mutation, authorized token, and read-back verification before writing. |
| Scoring weights are policy-driven, not independently calibrated. | `docs/scoring-calibration.md` explains the formula and recommended production calibration process. |

## Best demo path

1. Open the real DataHub asset page.
2. Show the browser extension panel auto-running Predicate from the asset URL.
3. Run Predicate against the same DataHub asset URN in the terminal as backup proof.
4. Open the local review server at `http://127.0.0.1:8765/review`.
5. Show one blocked asset, one allowed asset, and the hard finance stress case.
6. Run the 30-case curated benchmark.
7. Open the hosted static demo only as a public/screenshot-safe artifact.
8. Show the write-back receipt and explain that live mutation is intentionally
   gated.

## Recommended one-line claim

> Predicate adds a deterministic AI action gate to DataHub: it reads metadata
> evidence, checks an action predicate, and returns an explainable allow/block
> decision for humans and agents.
