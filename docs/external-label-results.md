# External Label Results

Two reviewers labeled 8 Predicate decisions across the local DataHub demo
assets.

## Result

```json
{
  "completed_labels": 8,
  "matches": 8,
  "disagreements": 0,
  "agreement_rate": 1.0
}
```

## How to say it

Use:

> Two reviewers labeled 8 demo decisions. Predicate matched all 8 labels on
> this small review set. This is early external agreement, not a production
> accuracy claim.

Avoid:

> Predicate is 100% accurate.

## Important nuance

One reviewer said `fct_users_created` and `SampleKafkaDataset` are allowed only
when AI explains the asset and does not provide recommendations. Those labels
are recorded under the lower-risk `answer-business-questions` capability, not
`autonomous-agent-action`.

That distinction is the point of Predicate: the same asset can be safe for
explanation and unsafe for autonomous action.
