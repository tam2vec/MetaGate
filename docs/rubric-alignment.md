# Elicit Rubric Alignment

Source: `Elicit - DataHub AI-Action Readiness Rubric.xlsx`.

This document maps the rubric to MetaGate's proof surface. It is deliberately
not a self-awarded score. The rubric asks whether a reviewer can reconstruct
the evidence, authorization, action, and outcome behind a decision.

## What The Rubric Changes

- Evidence comes before scores.
- `unavailable` is different from `absent` and lowers confidence rather than
  being silently treated as a missing metadata field.
- A blocked decision must stop the tool call, not only appear in the UI.
- High-impact actions need a named human approval path.
- Every decision needs a timestamp, decision ID, policy context, and replayable
  audit record.
- A score is a summary. It is never the reason an action is safe by itself.

## Evidence Matrix

| Rubric dimension | MetaGate proof in this repository | Status | Remaining proof or limitation |
| --- | --- | --- | --- |
| Coverage and discoverability (10) | Live catalog discovery, URN search, six-asset fixture, DataHub source guide | Implemented locally | A production deployment must define its in-scope asset population and coverage percentage. |
| Metadata completeness and semantic context (15) | Evidence extractor, glossary/owner/domain/tags checks, evidence-first review page | Implemented locally | Human approval of business definitions and sensitivity labels is deployment-specific. |
| Quality and trust (15) | Latest assertion checks, freshness checks, incident checks, profile rules, blocked action path | Implemented locally | A real deployment must expose current assertion run history and quality SLAs. |
| Lineage and provenance (15) | Dataset and column-lineage extraction, upstream incident investigator, source timestamps | Partial | Full record-level lineage and transformation provenance are not available from every DataHub deployment. |
| Access control and policy enforcement (15) | Local RBAC model, permission-aware contract, `/api/tool-call` fail-closed gate | Partial | The caller identity and DataHub authorization decision must be supplied by the host agent or deployment. |
| Actionability and tool integration (10) | Typed agent gate, dry-run contract, timeout/failure handling, repair-loop proof | Partial | A deployment-specific executor is still required for real writes and rollback. |
| Human oversight and operating model (10) | Review notes, steward override record, approval fields, RBAC documentation | Partial | A real organization must name approvers and define its emergency suspension SLA. |
| Observability, auditability, and change control (10) | SQLite history, decision IDs, before/after repair audit, policy and evidence trace | Implemented locally | Production use needs a shared durable audit store and retention policy. |
| Resilience and drift management (10) | Indexing poll, source timestamps, stale/unavailable states, refresh path | Partial | Production monitoring and alert delivery must be connected to the deployment. |
| End-to-end action safety (10) | Blocked tool calls, enforcement demo, 60 adversarial scenarios, repair loop | Implemented locally | Independent reviewers still need to validate the borderline cases. |

## Proof Commands

Run these from the MetaGate project directory.

```bash
# Unit and contract checks
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -p 'test*.py' -q

# Enforcement: the blocked path must not invoke the tool callback
PYTHONPATH=src python3 scripts/run_enforcement_demo.py

# Repair: blocked -> repair -> indexing poll -> re-evaluation -> audit
PYTHONPATH=src python3 scripts/run_repair_loop_demo.py --json

# Generated adversarial set; labels remain separate from generated cases
PYTHONPATH=src python3 scripts/generate_adversarial_scenarios.py --json
```

For a live deployment, also capture:

1. the DataHub dataset page with the exact URN;
2. the MetaGate evidence and decision response;
3. the DataHub write-back property or assertion, if the deployment supports
   the approved mutation;
4. the read-back response showing the same decision ID and timestamp.

## Human Review Protocol

The draft cases are in
`examples/benchmark/human-review-draft.csv`. A reviewer should see the asset
context and requested action, then answer in plain language:

1. Would you allow the requested AI action?
2. What single fact most influenced your answer?
3. What would you require before changing your answer?

The reviewer fills in `human_label`, `labeler_role`, and `label_reason`. Do not
pre-fill those fields from MetaGate's own output. The completed file can then
be evaluated with:

```bash
PYTHONPATH=src python3 scripts/evaluate_independent_labels.py \
  --labels examples/benchmark/external-reviewer-labels.csv
```

The existing 10 completed labels are an informal sanity check, not independent
held-out evidence. The blank draft cases are prompts, not reviewer answers.

## Honest Submission Language

Use this wording in the submission:

> MetaGate is an evidence-backed preflight gate for DataHub-aware AI actions.
> The local proof demonstrates current metadata checks, fail-closed tool
> enforcement, indexing-aware re-evaluation, audit history, and a repair loop.
> Native DataHub registration, live mutation/read-back, shared production audit
> storage, and independent human labels remain deployment or external-validation
> steps rather than claims of the local fixture.

This framing matches the rubric without presenting a fixture, simulated repair,
or proposed plugin contract as an already-installed production integration.
