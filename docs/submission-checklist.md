# Submission Checklist

## Repository readiness

- [ ] README opens with the product claim and the Predicate Certificate concept.
- [ ] Badges point to version, license, Python support, and CI.
- [ ] Architecture image renders in GitHub.
- [ ] Demo sequence image renders in GitHub.
- [ ] Quick-start command works from a fresh clone.
- [ ] `examples/outputs/README.md` explains that local outputs are fixture-based.
- [ ] Benchmark language says “curated benchmark” and avoids production claims.
- [ ] License, changelog, contributing guide, security policy, and code of conduct are present.
- [ ] No tokens, private DataHub URLs, screenshots with customer data, or local secrets are committed.

## Demo recording

- [ ] Record the real DataHub validation loop if available.
- [ ] Show the same asset URN before and after metadata repair.
- [ ] Show a blocked risky action.
- [ ] Show explainability output.
- [ ] Show readiness diff.
- [ ] Show write-back only if the deployment mutation is configured and verified.
- [ ] Keep the benchmark statement precise: 30 curated conformance checks pass with no unexpected allows or blocks.
- [ ] Have fixture-based backup outputs open before recording.

## Devpost assets

- [ ] Short description copied from `docs/devpost-submission-draft.md`.
- [ ] Long description copied and edited for the final hackathon prompt.
- [ ] Feature list includes certificates, admission control, explainability, diffs, policy profiles, and DataHub integration.
- [ ] Architecture section links to `docs/architecture.svg`.
- [ ] Limitations section distinguishes MVP, fixture proof, and live deployment proof.
- [ ] Demo video link added.
- [ ] GitHub repository URL added.
- [ ] Optional PyPI URL added only after publication.

## Final proof

- [ ] `pytest` passes.
- [ ] `PYTHONPATH=src python3 scripts/evaluate_benchmark.py` reports the expected benchmark result.
- [ ] `v0.1.0` release notes are ready.
- [ ] PyPI checklist is complete or explicitly marked post-submission.
- [ ] Upstream DataHub PR draft is ready.
