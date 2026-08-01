# Synthetic Reviewer Labels

These labels are not external benchmark proof.

They are deliberately synthetic examples that show reviewers how to label
Predicate decisions in a human, judgment-based way.

Use them for:

- demo narration
- reviewer guidance
- testing the independent-label scorer
- explaining what good external labels should sound like

Do not say:

> We have external benchmark labels.

Say:

> We include synthetic reviewer-style labels as examples. Real external labels
> are still being collected.

## File

```text
examples/benchmark/synthetic-reviewer-labels.csv
```

## Example

```text
i would block this for autonomous action. it has owner docs and lineage, but no
actual signup quality checks, so an agent could confidently act on bad counts.
```

That is better than:

```text
missing assertions
```

because it explains the human risk, not just the failed field.
