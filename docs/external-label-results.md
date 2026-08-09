# Informal Label Sanity Check

Two informal reviewers labeled 10 MetaGate decisions across the local DataHub
demo assets. These are useful sanity checks, but they are not an independent
held-out benchmark because the cases and decision context came from the
project demo:

- one reviewer with basic AI familiarity
- one reviewer with basic data/analytics familiarity

## Result

```json
{
  "completed_labels": 10,
  "matches": 10,
  "disagreements": 0,
  "agreement_rate": 1.0
}
```

## How to say it

Use:

> Two informal reviewers labeled 10 demo decisions: one with basic AI
> familiarity and one with basic data/analytics familiarity. MetaGate matched
> all 10 labels on this small sanity-check set. This is not independent
> benchmark evidence or a production accuracy claim.

Avoid:

> MetaGate is 100% accurate.

## Important nuance

One reviewer said `fct_users_created` and `SampleKafkaDataset` are allowed only
when AI explains the asset and does not provide recommendations. Those labels
are recorded under the lower-risk `answer-business-questions` capability, not
`autonomous-agent-action`.

That distinction is the point of MetaGate: the same asset can be safe for
explanation and unsafe for autonomous action.

## Next Review Round

Use the editable [`human-review-draft.csv`](../examples/benchmark/human-review-draft.csv)
for the next round. It contains 20 plain-language cases spanning allowed,
blocked, and borderline decisions. Leave the answer fields blank until a
reviewer independently gives their answer.
