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
needs to be blocked. ai should not work on it because there is no proof that the
number of people signing up is correct.
```

That is better than:

```text
missing assertions
```

because it explains the human risk, not just the failed field.

## More Human Examples

```text
i think it should be blocked because deleted-user data is important, and there
needs to be a check that the users were deleted for the right reason before
running ai on it.
```

```text
allowed as long as ai only explains the table and does not provide
recommendations.
```

```text
since money is involved, it needs to be checked properly and should be blocked
for now.
```
