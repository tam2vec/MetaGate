# External Benchmark Request

Use this when asking a reviewer, data steward, mentor, or judge-adjacent expert
to label MetaGate decisions independently.

## What to ask for

Ask the reviewer to judge whether each requested AI action should be allowed or
blocked based only on the sanitized asset metadata shown to them.

Do not ask them whether MetaGate is impressive. Ask them whether the decision
is correct.

## Minimum useful review

- 10 assets is useful.
- 20 assets is strong.
- 30+ assets is excellent.
- At least 2 high-risk assets should have two reviewers.
- Include both allowed and blocked cases.

## Reviewer instructions

Send this:

```text
I am benchmarking MetaGate, an AI admission controller for DataHub metadata.

For each row, please decide whether the requested AI action should be allowed or
blocked. Please do not use MetaGate's answer when labeling. Use your own
judgment from the sanitized metadata evidence.

What to return for each asset:

1. allowed or blocked
2. one-sentence reason
3. missing evidence terms, if blocked
4. whether the mistake would be severe if an AI agent acted anyway

The key question is:
Would you let an AI agent perform this action on this asset with the metadata
currently shown?
```

## What they should label

Use the CSV:

```text
examples/benchmark/independent-label-template.csv
```

For examples of human-sounding labels, see:

```text
examples/benchmark/synthetic-reviewer-labels.csv
```

Those rows are synthetic guidance only, not external proof.

Required columns:

| Column | What reviewer fills |
| --- | --- |
| `asset_urn` | DataHub asset URN |
| `platform` | hive, kafka, snowflake, dbt, etc. |
| `capability` | AI action being requested |
| `human_label` | `allowed` or `blocked` |
| `labeler_role` | data steward, analytics engineer, governance owner, etc. |
| `label_reason` | why they allowed or blocked it |
| `expected_failed_terms` | missing terms such as `assertions.present` |
| `notes` | sanitized comments |

## Good benchmark cases to include

Include these kinds of assets:

| Case type | Why it matters |
| --- | --- |
| Good documentation but no assertions | Catches shallow metadata quality |
| Owner present but stale freshness | Tests whether trust can expire |
| Glossary present but contradictory definition | Tests semantic governance |
| Lineage present but missing column lineage | Tests action-specific risk |
| Finance or privacy-impacting asset | Tests high-risk thresholds |
| Streaming asset | Tests non-table metadata expectations |
| Fully governed asset | Confirms MetaGate can allow, not only block |

## Scoring after labels

Run:

```bash
PYTHONPATH=src python3 scripts/evaluate_independent_labels.py \
  --labels examples/benchmark/independent-label-template.csv
```

Report:

- total labeled cases
- agreement rate
- unexpected allows
- unexpected blocks
- most important disagreement

Unexpected allows are the most serious because they mean MetaGate allowed an
action a human reviewer would have blocked.

## Honest wording before labels exist

Use:

> MetaGate passes 30/30 curated conformance checks. Independent benchmark
> labeling is prepared and ready for external reviewers.

Do not use:

> MetaGate is 100% accurate.
