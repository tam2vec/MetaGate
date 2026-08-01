# Independent Benchmark Protocol

The built-in 30-case benchmark is a curated conformance suite. It proves that
Predicate behaves as intended on known ready, missing, stale, incomplete, and
contradictory metadata states.

For an external benchmark, use independently labeled assets.

## Label file

Start with:

```text
examples/benchmark/independent-label-template.csv
```

Required columns:

| Column | Meaning |
| --- | --- |
| `asset_urn` | DataHub asset URN |
| `platform` | Data platform, such as hive, snowflake, kafka, dbt |
| `capability` | Requested AI action |
| `human_label` | `allowed` or `blocked` |
| `labeler_role` | Who labeled it, such as data steward or governance owner |
| `label_reason` | Human reason for the label |
| `expected_failed_terms` | Expected blocked predicate terms, if any |
| `notes` | Sanitized context |

## Recommended set

- at least 20 assets from one real DataHub deployment
- at least 3 platforms if available
- at least 2 capabilities
- at least 2 independent labelers for high-risk assets
- no customer secrets, personal data, or private table contents

## Report honestly

Until this file is filled by reviewers outside the project rules, say:

> Predicate passes 30/30 curated conformance checks. Independent benchmark
> labeling is prepared but not yet completed.

After labels are complete, report:

- total labeled assets
- agreement rate between Predicate and human labels
- unexpected allows
- unexpected blocks
- examples of false allows or false blocks

Unexpected allows matter most because they mean Predicate allowed an action a
human reviewer would have blocked.
