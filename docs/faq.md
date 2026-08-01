# FAQ

## Why not use an LLM to decide?

The admission decision is deterministic and reproducible. An LLM can explain
the result, but it cannot override the policy engine.

## Why DataHub?

DataHub already contains the ownership, definitions, lineage, quality, usage,
and incident evidence required to make a defensible decision.

## Why capability-based certification?

An asset may be safe to explain but unsafe to modify. Capability gates express
that difference directly.

## Why keep readiness and confidence separate?

An asset can have strong visible evidence but incomplete graph coverage. The
separate confidence score prevents the system from overstating certainty.

## Why not use one readiness score?

One score hides which action is safe. The score is a summary; the certificate,
gaps, and context contract are the decision artifacts.
