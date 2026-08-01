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
i would block it. i can see what the table is and who owns it, but i do not see
proof that the signup numbers are actually checked. letting an agent act on
that feels like asking for a confident mistake.
```

That is better than:

```text
missing assertions
```

because it explains the human risk, not just the failed field.

## More Human Examples

```text
nope. deleted users is not a casual table. before an agent does anything here,
i would want proof that the dates, counts, and user states are being checked
properly.
```

```text
for a basic explanation, yes. the agent can say what this table is for. but i
would not let it recommend actions or change anything based on it yet.
```

```text
hard block. this is money-adjacent, and the definitions are not clean enough.
if people disagree on what the number means, an agent should not be making
decisions from it.
```
