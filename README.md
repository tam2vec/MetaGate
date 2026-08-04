# Predicate

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](pyproject.toml)
[![CI](https://img.shields.io/badge/ci-unittest%20%2B%20benchmark-informational.svg)](.github/workflows/ci.yml)

**Know when AI is allowed to act.**

Enterprise data already has a control plane: owners, glossary terms, lineage,
assertions, freshness, incidents, usage, and policy. AI agents mostly ignore it.

Predicate turns that metadata into a deterministic action check:

```json
{
  "action": "autonomous-agent-action",
  "predicate": "ownership.present && lineage.present && assertions.present && incidents.open == 0",
  "result": false,
  "failed_terms": ["assertions.present"],
  "decision": "blocked"
}
```

No metadata proof, no AI action.

## The Demo

Predicate is an AI admission controller for DataHub. Ask whether an agent may
explain, summarize, modify, or act on a data asset; Predicate returns allowed or
blocked with the exact missing evidence.

| Proof | Link |
| --- | --- |
| Public Predicate Review | [Open the hosted review](https://leafy-maamoul-4acf4b.netlify.app/?api=https://predicate-ixz0.onrender.com) |
| Local DataHub runbook | [Live DataHub Validation](docs/live-datahub-validation.md) |
| Browser extension prototype | [DataHub Panel Prototype](examples/browser-extension/README.md) |
| Hackathon DataHub sources | [Load and review the provided datasets](docs/hackathon-datahub-sources.md) |

The hosted page is API-backed and labels its source. In the current safe
fixture mode it says `Mode: public API fixture`; after a reachable DataHub is
configured on Render it says `Mode: live DataHub API`. The real proof path
must always be verified through `/api/status`, not inferred from appearance.

## One Command

```bash
python3 -m pip install -e ".[datahub]"
export DATAHUB_GRAPHQL_URL="http://localhost:8080/api/graphql"

predicate \
  "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)" \
  --policy examples/policies/enterprise_ai.yml \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --request-capability autonomous-agent-action
```

Evaluations are read-only by default. Live DataHub write-back requires the
explicit `--enable-writeback` flag plus deployment-approved mutation documents.

The live adapter asks DataHub for assertion run history, active incident
status, usage buckets, fine-grained lineage, and freshness assertion results.
When a deployment does not expose one of those fields, Predicate labels it
`unavailable` and lowers confidence; it does not call the evidence “missing”
or quietly reuse a recorded demo result.

Example result:

```json
{
  "allowed": false,
  "capability": "autonomous-agent-action",
  "reason": "Missing required evidence: assertions; Readiness score below 92.0; Confidence below 88.0"
}
```

## What Judges Should Notice

- Predicate reads DataHub metadata and converts it into deterministic go/no-go
  decisions for AI actions.
- It can allow one asset and block another under the same policy.
- It explains the failed terms, not just a generic score.
- It has a local API-backed review app, browser extension prototype, CLI, SDK,
  Docker path, tests, and curated benchmark.
- It is read-only by default; write-back is explicit and deployment-gated.
- Review decisions, notes, and steward overrides persist locally in SQLite.

## Production Path: Predicate Preflight

The tight production story is:

> Predicate is a DataHub preflight gate. Before an AI
> workflow touches a dataset, it checks whether the metadata is decision-ready,
> writes a governed Context Contract back into DataHub, and either constrains
> the agent or blocks it with an auditable reason.

Proof layers:

| Layer | Artifact |
| --- | --- |
| DataHub preflight action | [Predicate Preflight](examples/datahub-preflight-action/README.md) |
| Context Contract write-back shape | [AI Context Contract aspect](examples/datahub-preflight-action/context-contract-aspect.json) |
| Private deployment adapter | [Private Deployment Adapter](docs/private-deployment-adapter.md) |
| Unsafe-answer benchmark framing | [Unsafe-Answer Reduction Benchmark](docs/unsafe-answer-reduction-benchmark.md) |
| Auth and RBAC enforcement model | [RBAC Enforcement Model](docs/rbac-enforcement-model.md) |

## Proof From Local DataHub

Predicate was validated against a local DataHub quickstart seeded with sample
metadata.

| DataHub asset | Capability | Decision | Why |
| --- | --- | --- | --- |
| `SampleHiveDataset` | `autonomous-agent-action` | allowed | Required evidence present |
| `fct_users_created` | `autonomous-agent-action` | blocked | Missing assertions; score and confidence below threshold |
| `fct_users_deleted` | `autonomous-agent-action` | blocked | Missing assertions; score and confidence below threshold |
| `SampleKafkaDataset` | `autonomous-agent-action` | blocked | Stress case with incomplete governance evidence |

For a harder run, see [Difficult DataHub Run](docs/difficult-datahub-run.md).

## Local Review App

From the project folder, start the live review once:

```bash
./scripts/start_predicate_review.sh
```

Then open `http://127.0.0.1:8765/review`. After metadata changes in DataHub,
use **Refresh DataHub check** in the page. You do not rerun a separate CLI
command for every asset.

```bash
predicate-review \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --policy examples/policies/enterprise_ai.yml
```

Open `http://127.0.0.1:8765/review`.

The review app shows the asset, decision, readiness, confidence, failed terms,
remediation plan, capability matrix, audit trail, and write-back queue.
CLI and Review use the same direct-lineage scope by default. Override both with
the same `--max-hops` value if a deeper graph is needed.

Human review notes submitted in the local Review app are appended to
`.context-gradient/review-notes.jsonl` and can be read through `/api/reviews`.
The hosted static demo cannot persist server-side notes, so it keeps a
browser-local copy instead.

## Evidence correctness checks

Run the unit and schema-contract checks without a DataHub server:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -q
```

To run the opt-in test against the actual deployment used for the demo:

```bash
export DATAHUB_GRAPHQL_URL="http://localhost:8080/api/graphql"
export PREDICATE_LIVE_DATAHUB_URN="urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)"
PYTHONPATH=src python3 -m unittest tests.test_datahub_schema -v
```

The live test is skipped when `DATAHUB_GRAPHQL_URL` or
`PREDICATE_LIVE_DATAHUB_URN` is absent. Run it with the local DataHub
containers up; a green fixture test is not a substitute for this deployment
check.

To compare current fixture decisions with the human review file:

```bash
PYTHONPATH=src python3 scripts/evaluate_independent_labels.py \
  --labels examples/benchmark/synthetic-reviewer-labels.csv \
  --datahub-file examples/data/difficult_datahub_graph.json \
  --policy examples/policies/enterprise_ai.yml
```

Rows whose asset is not in the selected graph are reported as unevaluated;
they are never counted as agreement.

## Results

```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 scripts/evaluate_benchmark.py
```

- automated tests and DataHub schema-contract checks passing
- 30/30 curated policy conformance checks passing
- 0 unexpected allows
- 0 unexpected blocks
- Curated states covered: ready, missing, stale, incomplete, contradictory

The benchmark validates this repository's policy behavior. It is not a
production accuracy, precision, or recall claim.

## What Is Real vs Prototype

Real in this MVP:

- CLI and SDK decision engine
- Live reads from local DataHub GraphQL
- Local API-backed Predicate Review app
- Browser extension prototype that detects DataHub asset URNs
- Dockerized review API path
- Safe write-back payloads and receipts
- Installed commands: `predicate` and `predicate-review`
- Tests, curated benchmark, contribution guide, release notes, and docs

Prototype or future integration:

- The embedded DataHub panel is an intended product experience, not a packaged
  production DataHub plugin.
- The public hosted page uses sanitized data, not a public DataHub deployment.
- Live write-back mutations require deployment-supported DataHub GraphQL
  mutations.
- Independent benchmark scoring exists, but external reviewers still need to
  label held-out cases.

## Core Capabilities

- Evidence extraction for ownership, glossary, lineage, assertions, incidents,
  freshness, usage, and policy
- Capability-based certification
- Readiness and confidence scoring
- Predicate Certificate output
- Gap classification: missing, stale, incomplete, contradictory
- Remediation planning
- Policy simulation
- Readiness diffs and trust timeline
- Audit logging
- YAML policy profiles

## Security Model

Predicate is designed to be safe by default:

- read-only evaluation unless write-back mutations are explicitly configured
- DataHub token stays server-side in local/private deployments
- public demo uses sanitized fixture data, never a private DataHub token
- write-back is deployment-owned and gated by approved GraphQL mutation documents
- recommended production flow separates requester, reviewer, and metadata owner

## SDK

```python
from predicate import ReadinessEngine, load_policy
from context_gradient.datahub.adapter import DataHubEvidenceExtractor
from context_gradient.datahub.mock_client import FileDataHubClient

policy = load_policy("examples/policies/enterprise_ai.yml")
client = FileDataHubClient("examples/data/datahub_graph.json")
bundle = DataHubEvidenceExtractor(client).bundle(
    "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)"
)
certificate = ReadinessEngine(policy).certify(bundle)
print(certificate.as_dict())
```

## Important Docs

- [3-minute demo script](docs/demo-script.md)
- [Judge proof](docs/judge-proof.md)
- [Production gap closure](docs/production-gap-closure.md)
- [Proof layers](docs/proof-layers.md)
- [Production readiness](docs/production-readiness.md)
- [Public API fixture demo](docs/public-live-demo.md)
- [Live review app](docs/live-review-app.md)
- [Capability matrix](docs/capability-matrix.md)
- [Trust timeline](docs/trust-timeline.md)
- [Policy catalog](docs/policy-catalog.md)
- [Write-back safety](docs/writeback-safety.md)
- [Independent benchmark protocol](docs/independent-benchmark-protocol.md)
- [External label results](docs/external-label-results.md)
- [Unsafe-answer reduction benchmark](docs/unsafe-answer-reduction-benchmark.md)
- [Private deployment adapter](docs/private-deployment-adapter.md)
- [RBAC enforcement model](docs/rbac-enforcement-model.md)
- [External benchmark request](docs/external-benchmark-request.md)
- [Synthetic reviewer labels](docs/synthetic-reviewer-labels.md)
- [Screenshots checklist](docs/screenshots-checklist.md)

## DataHub Version Notes

Some DataHub GraphQL versions require dataset fields to be queried through a
`Dataset` fragment. If the default query reports `FieldUndefined` on `Entity`,
set `DATAHUB_ENTITY_QUERY` to a deployment-compatible query. See
[Live DataHub Validation](docs/live-datahub-validation.md).

## License

Apache-2.0
