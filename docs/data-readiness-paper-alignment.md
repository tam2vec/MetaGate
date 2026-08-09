# Data Readiness Alignment

MetaGate asks a practical question: **is there enough current, understandable
evidence for this specific AI action?** The attached paper, *Laying the
Foundation: Why Data Readiness is the Cornerstone of Successful AI Initiatives*,
is useful because it makes the same point from a broader data-management
perspective: readiness is not one quality flag and it is not a score alone.

This note records how the paper's ideas map to MetaGate. It is an alignment
reference, not independent validation of MetaGate and not a claim that
MetaGate can measure raw-data truth without a DataHub quality signal.

## Four readiness lenses

| Paper lens | MetaGate evidence | Honest interpretation |
| --- | --- | --- |
| Precision and quality | Latest DataHub assertions, freshness, incidents, and action thresholds | The decision uses the latest quality evidence DataHub returned. MetaGate does not independently prove that a business value is true. |
| Thoroughness | Required evidence profiles, metadata coverage, schema, and column-lineage coverage | Required metadata is present, complete, current, or explicitly unavailable. Missing metadata is not proof that the underlying data is wrong. |
| Contextual coherence | Glossary terms, domains, ownership, policy, dataset-type profiles, and human approval paths | The action is evaluated in business and governance context, rather than against one universal checklist. |
| Origin tracking | Dataset lineage, column lineage, source timestamps, graph scope, and incident investigation | A reviewer can trace the decision to the asset's available upstream and downstream evidence. |

## Quality dimensions that require real checks

The paper separates quality properties that are easy to blur together:

- **Completeness:** are required fields, metadata, and relevant cases covered?
- **Accuracy:** do values represent the real-world thing they claim to represent?
- **Consistency:** do related fields and systems agree?
- **Reliability:** does the signal remain stable across repeated observations?
- **Timeliness:** is the information current for its intended use?
- **Validity and uniqueness:** do values obey declared rules and avoid unintended duplicates?

MetaGate treats these dimensions as follows:

1. It can enforce a quality dimension when a current DataHub assertion exposes
   that result, including the assertion name, latest status, timestamp, and
   failure detail.
2. It can assess metadata completeness, timeliness, lineage, context, and
   governance directly from the DataHub evidence it can read.
3. It marks a required signal as `unavailable` when the deployment does not
   expose it. It does not silently convert that unknown into a passing check.
4. It does **not** claim to calculate raw-data accuracy, bias, validity,
   uniqueness, or representational coverage from schema metadata alone. Those
   require real quality assertions, profiles, samples, or steward review.

That boundary matters: a clean schema can still contain incorrect or biased
values, while a missing DataHub assertion means “not verified,” not
“definitely bad.”

## Governance and operating model

The paper also emphasizes that readiness depends on people and decisions, not
only tooling. MetaGate represents that layer with:

- an accountable owner and escalation path;
- action-specific policies and dataset profiles;
- human approval requirements for high-impact actions;
- a constraint contract for the agent;
- a fail-closed tool boundary;
- decision IDs, timestamps, evidence facts, and review history;
- before-and-after repair records when a deployment supplies an approved mutation.

Lifecycle controls such as retention, deletion, and access review remain
deployment-specific. MetaGate can require evidence that those controls exist,
but it cannot invent an organization's policy or authorization decision.

## Stronger evidence in a real DataHub deployment

To turn these quality lenses into stronger evidence, configure DataHub
assertions for important fields and business rules, for example:

- row-count and freshness SLAs;
- non-null and uniqueness checks for identifiers;
- accepted ranges and non-negative checks for financial values;
- reconciliation checks between source and reporting tables;
- schema compatibility and consumer-lag checks for Kafka;
- feature drift and training-serving consistency checks for ML data;
- validity checks for coordinates and geographic boundaries;
- completeness checks for required categories or time periods.

Then run MetaGate against the deployment and verify that each result contains
the latest assertion status and timestamp. The decision is stronger because it
is evidence-backed; the score itself remains only a summary.

## Honest submission language

> MetaGate applies a DataHub-aware readiness gate before an AI action. It
> distinguishes metadata completeness, freshness, context, provenance, and
> quality evidence, and it fails closed when required evidence is missing or
> unavailable. MetaGate does not claim that metadata alone proves raw-data
> accuracy; that claim requires current DataHub assertions or independent
> steward-reviewed evidence.
