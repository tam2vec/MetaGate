# Proof Layers

MetaGate is the hackathon project name. The production pattern is a DataHub
preflight gate: before an AI workflow touches a dataset, the gate checks whether
the metadata is decision-ready, writes a governed Context Contract back into
DataHub, and either constrains the agent or blocks it with an auditable reason.

This turns the remaining gaps into a credible production path.

## 1. DataHub Preflight Integration

Artifact:

- `examples/datahub-preflight-action/`
- `examples/datahub-embed/`
- `examples/browser-extension/`

Production shape:

1. User opens a DataHub dataset.
2. User clicks **Request AI Readiness**.
3. DataHub sends the asset URN and requested capability to MetaGate.
4. MetaGate reads DataHub metadata through GraphQL.
5. MetaGate returns a Context Contract.
6. DataHub shows `PROCEED`, `CAUTION`, or `BLOCKED`.

Hackathon proof:

- browser extension auto-detects the DataHub asset URN
- local review API evaluates that URN
- intended DataHub panel shows decision and repairs

Honest claim:

> MetaGate proves the automatic preflight UX through a browser extension
> prototype. A packaged DataHub plugin is the next integration step.

## 2. Real DataHub-Backed Demo

Artifact:

- `docs/live-datahub-validation.md`
- `examples/outputs/live-runs.json`
- `examples/outputs/live-datahub-proof.html`

Production shape:

Run against a real DataHub instance with public demo metadata such as NYC Taxi
or dbt Jaffle Shop. Ingest schema, owners, lineage, tags, glossary terms, usage,
freshness, and assertions.

Hackathon proof:

- local DataHub quickstart
- seeded public/sample metadata
- MetaGate CLI/API reads DataHub GraphQL
- public site uses sanitized fixture data instead of exposing a DataHub token

Honest claim:

> The public demo is sanitized. The DataHub-backed proof runs locally or inside
> a private DataHub deployment.

## 3. Context Contract Write-Back

Artifact:

- `examples/outputs/context-contract.json`
- `examples/outputs/writeback-payload.json`
- `examples/outputs/writeback-receipt.json`
- `docs/writeback-safety.md`

Production shape:

MetaGate writes an **AI Context Contract** custom aspect or equivalent metadata
field onto the DataHub asset:

```json
{
  "status": "BLOCKED",
  "confidence": 86.25,
  "readiness_score": 91.22,
  "missing_evidence": ["assertions.present"],
  "recommended_constraints": [
    "Do not allow autonomous agent action.",
    "Allow read-only business question answering only if policy permits."
  ],
  "decision_record": "metagate://decision/cg-2026-08-01-0001",
  "evaluated_at": "2026-08-01T00:00:00Z"
}
```

Hackathon proof:

- safe write-back payload and receipt exist
- live mutation is gated behind deployment-approved GraphQL mutation documents
- review UI shows the write-back queue and Context Contract semantics

Honest claim:

> MetaGate is read-only by default. It can generate the governed Context
> Contract payload; live DataHub write-back is enabled only when the deployment
> owner supplies a supported mutation.

## 4. External Benchmark Labels

Artifact:

- `docs/external-benchmark-request.md`
- `examples/benchmark/independent-label-template.csv`
- `scripts/evaluate_independent_labels.py`

Production shape:

Do not claim enterprise labels until external reviewers label cases. The right
metric is not generic model accuracy. The right metric is unsafe-answer
reduction.

Evaluation setup:

1. Create 10-20 analytics questions across the demo datasets.
2. Label each as `safe`, `risky`, or `blocked`.
3. Run a baseline AI answer without MetaGate gating.
4. Run the same request with MetaGate gating.
5. Count unsafe answers prevented by MetaGate.

Report:

- total questions
- unsafe baseline answers
- unsafe answers after MetaGate gating
- unsafe-answer reduction
- conservative blocks

Honest claim:

> MetaGate passes 30/30 curated policy conformance checks. Independent labels
> are prepared and should measure unsafe-answer reduction.

## 5. Private Deployment Adapter

Artifact:

- `docs/private-deployment-adapter.md`
- `examples/data/difficult_datahub_graph.json`
- `docs/difficult-datahub-run.md`

Production shape:

MetaGate runs inside the enterprise boundary. It consumes metadata and optional
sampled profiles by default, not raw rows. A private deployment points MetaGate
at DataHub GraphQL and supplies policy thresholds.

Checks use:

- ownership
- lineage
- glossary definitions
- freshness
- assertions
- incidents
- access policy
- precedent from previous decision records

Hackathon proof:

- difficult finance fixture blocks a clean-looking schema because owner,
  lineage, assertions, freshness, and metric definitions are not trustworthy

Honest claim:

> MetaGate can run against private DataHub instances because the decision is
> based on governed metadata, not raw table contents by default.

## 6. Auth And RBAC Enforcement Model

Artifact:

- `docs/rbac-enforcement-model.md`
- public review UI Security & RBAC panel

Production shape:

- DataHub policies decide who can request a verdict.
- Only designated stewards can override `BLOCKED`.
- Every override requires a reason.
- Every override becomes part of the decision record.
- The AI agent inherits the requester's DataHub permissions.
- The agent only sees metadata and datasets the requester can see.

Hackathon proof:

- read-only default
- server-side DataHub token
- write-back mutation gate
- documented separation of requester, reviewer, metadata owner, and approver

Honest claim:

> MetaGate defines the enforcement model and safe defaults. Production auth and
> RBAC are deployment responsibilities wired through DataHub policy controls.
