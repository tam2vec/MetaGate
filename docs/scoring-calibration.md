# Scoring and Calibration

Predicate uses deterministic policy scoring. It does not train a model, infer
semantic truth, or claim production accuracy.

## Readiness score

Readiness answers: "How complete and healthy is the metadata for this asset?"

Each evidence item receives a policy weight. The engine gives full credit for
evidence that is present, complete, current, and not contradictory.

| Evidence state | Score factor |
| --- | ---: |
| Present, complete, current | 1.00 |
| Incomplete | 0.65 |
| Stale | 0.45 |
| Contradictory | 0.20 |
| Missing | 0.00 |

The weighted result is converted to a 0-100 score. Connected upstream and
downstream assets can reduce the score through graph propagation when their own
metadata is weak.

## Confidence

Confidence answers: "How much should the system trust the observed evidence?"

The current confidence formula combines:

- evidence coverage: how many expected evidence signals are present
- source confidence: confidence values attached to those evidence signals
- contradiction penalty: conflicting metadata lowers certainty
- graph coverage: missing expected neighbors reduces confidence

The local confidence is:

```text
(coverage * 60) + (average source confidence * 40) - (contradiction rate * 35)
```

Then graph coverage scales that value:

```text
confidence = local_confidence * (0.75 + 0.25 * graph_coverage)
```

The result is clamped between 0 and 100.

## Capability thresholds

Different AI actions require different standards. In
`examples/policies/enterprise_ai.yml`:

| Capability | Minimum score | Minimum confidence | Required evidence |
| --- | ---: | ---: | --- |
| `answer-business-questions` | 78 | 75 | ownership, glossary, freshness, policy |
| `generate-executive-metrics` | 84 | 80 | ownership, glossary, lineage, assertions, freshness, policy |
| `autonomous-agent-action` | 92 | 88 | ownership, glossary, lineage, assertions, incidents, freshness, usage, policy |

An action is allowed only when all three checks pass:

```text
readiness_score >= capability.minimum_score
confidence >= capability.minimum_confidence
all required evidence is present, complete, current, and non-contradictory
```

## Why this is good for an MVP

The scoring is transparent, inspectable, and policy-controlled. A data platform
team can change weights and thresholds without retraining anything.

## What remains for production

Production calibration should use independently labeled enterprise cases. Those
labels should come from data stewards, governance teams, or incident reviews,
not from the Predicate rules themselves.

Recommended production calibration set:

- 20-30 ready assets across different platforms
- 20-30 blocked assets with known missing metadata
- 10-20 stale or incident-affected assets
- 10-20 assets with contradictory ownership, glossary, or quality signals
- a held-out set that was not used while tuning weights

The repository's `30/30` benchmark is therefore a conformance check for this
MVP, not a universal accuracy claim.
