# Upstream DataHub Skills PR

## Title

`docs: add decision-readiness preflight for agent quality checks`

## Summary

Adds a read-only decision-readiness preflight reference to the DataHub quality
skill. It helps agents assess whether metadata is current and sufficient for a
requested action without collapsing deployment limitations into missing data.

## What it adds

- explicit `Present`, `Absent`, `Unavailable`, and `Stale` evidence states;
- latest-result handling for assertions;
- timestamp-aware freshness and incident checks;
- lineage and column-lineage coverage guidance;
- action-specific gates for explanation, metric generation, and autonomous
  action;
- a compact, evidence-backed JSON response shape and concrete repair guidance.

## Why

DataHub quality skills already expose assertions and incidents. Agents also need
a consistent way to decide whether those facts are sufficient for a proposed
action, especially when GraphQL support differs between deployments. This keeps
the workflow read-only by default and makes uncertainty visible to the user.

## Validation

- Documentation-only change.
- Follows the repository's Conventional Commit guidance.
- No DataHub credentials or private metadata are included.

## Reviewer note

The proposed reference is intentionally deployment-aware: an unsupported or
failed field is reported as unavailable rather than treated as proof that the
metadata does not exist.
