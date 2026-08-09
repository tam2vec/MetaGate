# MetaGate

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](pyproject.toml)
[![CI](https://img.shields.io/badge/ci-unittest%20%2B%20benchmark-informational.svg)](.github/workflows/ci.yml)

**Know when AI is allowed to act.**

Enterprise data already has a control plane: owners, glossary terms, lineage,
assertions, freshness, incidents, usage, and policy. AI agents mostly ignore it.

MetaGate turns that metadata into a deterministic action check:

```json
{
  "action": "autonomous-agent-action",
  "metagate": "ownership.present && lineage.present && assertions.present && incidents.open == 0",
  "result": false,
  "failed_terms": ["assertions.present"],
  "decision": "blocked"
}
```

No metadata proof, no AI action.

## The Demo

MetaGate is an AI admission controller for DataHub. Ask whether an agent may
explain, summarize, modify, or act on a data asset; MetaGate returns allowed or
blocked with the exact missing evidence.

| Proof | Link |
| --- | --- |
| Public MetaGate Review | [Open the hosted review](https://leafy-maamoul-4acf4b.netlify.app/?api=https://metagate-ixz0.onrender.com) |
| Local DataHub runbook | [Live DataHub Validation](docs/live-datahub-validation.md) |
| Browser extension prototype | [DataHub Panel Prototype](examples/browser-extension/README.md) |
| Agent integration | [MetaGate MCP server](examples/mcp/README.md) |
| Agent Registry + Service Catalog governance | [Verified execution chain](docs/agent-registry-service-catalog.md) |
| Hackathon DataHub sources | [Load and review the provided datasets](docs/hackathon-datahub-sources.md) |
| Judge rubric alignment | [Elicit rubric to MetaGate proof map](docs/rubric-alignment.md) |
| Data readiness foundation | [Paper alignment and quality boundaries](docs/data-readiness-paper-alignment.md) |
| Production proof runbook | [Tool gate, repair loop, MCP, write-back, and adversarial proof](docs/production-proof.md) |

The hosted page is API-backed and labels its source. In the current safe
fixture mode it says `Mode: public API fixture`; after a reachable DataHub is
configured on Render it says `Mode: live DataHub API`. The real proof path
must always be verified through `/api/status`, not inferred from appearance.

MetaGate also verifies the execution path before a governed action runs:
registered agent -> authorized skill -> registered tool/API -> owning service.
The requested capability must be in the skill's allowed action list, and the
same chain is carried into the agent constraint contract and enforced again at
the tool boundary. The local demo catalog mirrors DataHub's Agent Registry and
Service Catalog vocabulary; it is explicitly labeled as a local adapter rather
than a claim that the OSS quickstart has Cloud-only registry entities.

## Judge path: five minutes

1. Start DataHub with the [Quickstart Guide](https://docs.datahub.com/docs/quickstart).
2. Load a rich graph: `datahub datapack load showcase-ecommerce --force`.
3. Start MetaGate with `./scripts/start_metagate_review.sh`.
4. Open the review page and choose **Hackathon DataHub resources** -> **Find loaded assets**.
5. MetaGate automatically discovers and scores the datasets currently loaded
   in DataHub. Select a discovered URN and request an AI action. The decision, evidence,
   failed terms, and remediation come from that asset's current DataHub metadata.

The page also links the official [MCP Server](https://github.com/acryldata/mcp-server-datahub),
[Agent Context Kit](https://docs.datahub.com/docs/dev-guides/agent-context/agent-context),
[DataHub Skills](https://docs.datahub.com/docs/dev-guides/agent-context/skills),
[Analytics Agent](https://docs.datahub.com/docs/features/feature-guides/analytics-agent),
and the hackathon's NYC Taxi, Healthcare, and Fiction Retail scenarios. See the
[resource lab guide](docs/hackathon-datahub-sources.md) for the full source list.

For a repeatable presentation without Docker or a live DataHub, use
`./scripts/start_metagate_demo.sh`. It serves the same six-asset proof fixture
every time and labels itself as a fixture. It is not a substitute for the live
DataHub run; it is the reliable fallback for a judge who needs to see the full
decision flow immediately.

## One Command

```bash
python3 -m pip install -e ".[datahub]"
export DATAHUB_GRAPHQL_URL="http://localhost:8080/api/graphql"

metagate \
  "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)" \
  --policy examples/policies/enterprise_ai.yml \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --request-capability autonomous-agent-action
```

Evaluations are read-only by default. Live DataHub write-back requires the
explicit `--enable-writeback` flag plus deployment-approved mutation documents.

The live adapter asks DataHub for assertion run history, active incident
status, usage buckets, fine-grained lineage, and freshness assertion results.
When a deployment does not expose one of those fields, MetaGate labels it
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

- MetaGate reads DataHub metadata and converts it into deterministic go/no-go
  decisions for AI actions.
- It can allow one asset and block another under the same policy.
- It explains the failed terms, not just a generic score.
- It has a local API-backed review app, browser extension prototype, CLI, SDK,
  Docker path, tests, and curated benchmark.
- It is read-only by default; write-back is explicit and deployment-gated.
- Review decisions, notes, and steward overrides persist locally in SQLite.
- A blocked `/api/tool-call` request fails closed before the tool callback runs.
- The review page exposes a repair-loop proof and 60 synthetic adversarial cases;
  synthetic scenarios are clearly separate from independent human labels.

## Production Path: MetaGate Preflight

The tight production story is:

> MetaGate is a DataHub preflight gate. Before an AI
> workflow touches a dataset, it checks whether the metadata is decision-ready,
> writes a governed Context Contract back into DataHub, and either constrains
> the agent or blocks it with an auditable reason.

Proof layers:

| Layer | Artifact |
| --- | --- |
| DataHub preflight action | [MetaGate Preflight](examples/datahub-preflight-action/README.md) |
| Agent tool integration | [MetaGate MCP server](examples/mcp/README.md) |
| Context Contract write-back shape | [AI Context Contract aspect](examples/datahub-preflight-action/context-contract-aspect.json) |
| Private deployment adapter | [Private Deployment Adapter](docs/private-deployment-adapter.md) |
| Unsafe-answer benchmark framing | [Unsafe-Answer Reduction Benchmark](docs/unsafe-answer-reduction-benchmark.md) |
| Auth and RBAC enforcement model | [RBAC Enforcement Model](docs/rbac-enforcement-model.md) |

## Proof From Local DataHub

MetaGate was validated against a local DataHub quickstart seeded with sample
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
./scripts/start_metagate_review.sh
```

If MetaGate was installed to start at login, it runs from a copied runtime at
`~/MetaGateRuntime`. After changing source files, replace that runtime with:

```bash
METAGATE_FORCE_RESTART=1 ./scripts/start_metagate_review.sh
```

The launcher prints its build ID and asset scope. If the page ever shows an
older build, run the installer again; it copies the current project, restarts
the login service, and waits for `/healthz` before reporting success:

```bash
./scripts/install_metagate_autostart.sh
```

In live mode the connected DataHub catalog is authoritative. MetaGate
paginates DataHub's dataset search and evaluates every dataset returned on
each refresh (`METAGATE_MAX_ASSETS=0` means no cap). It does not inject the
six proof URNs into a live catalog run. If discovery fails or returns no
datasets, the page shows the catalog problem and does not silently substitute
fixture data. The six proof assets are available only in the explicit fixture
demo. Loading another DataHub pack and pressing **Refresh DataHub check**
rescans the catalog; no per-asset terminal command is required.

Before presenting the demo, check the four local prerequisites in one shot:

```bash
metagate-doctor
```

It reports DataHub GraphQL, the review API, the extension source, MetaGate's
local MCP server, and the optional official DataHub MCP separately. The
official server is not considered configured until its separate probe succeeds.
A failed required check is a setup problem, not a blocked dataset.

Then open `http://127.0.0.1:8765/review`. After metadata changes in DataHub,
use **Refresh DataHub check** in the page. You do not rerun a separate CLI
command for every asset.

```bash
metagate-review \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --policy examples/policies/enterprise_ai.yml
```

Open `http://127.0.0.1:8765/review`.

The review app shows the asset, decision, readiness, confidence, failed terms,
remediation plan, capability matrix, audit trail, and write-back queue.
The API status also exposes a build ID, source mode, configured asset count,
resolved asset count, and any configured assets that could not be read. This
makes a stale deployment or an incomplete DataHub catalog visible instead of
silently changing the scorecard.
CLI and Review use the same direct-lineage scope by default. Override both with
the same `--max-hops` value if a deeper graph is needed.

The review page also exposes three proof endpoints so the behavior can be
verified without reading a long terminal transcript:

```bash
# Evidence-first decision: facts, statuses, gaps, and constraint contract
curl -sG http://127.0.0.1:8765/api/evidence \
  --data-urlencode 'urn=urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)' \
  --data-urlencode 'capability=autonomous-agent-action' | python3 -m json.tool

# Evaluate the connected catalog with the same policy and scope as Review
curl -sG http://127.0.0.1:8765/api/scan \
  --data-urlencode 'capability=autonomous-agent-action' \
  --data-urlencode 'limit=0' | python3 -m json.tool

# Prove blocked requests never invoke the tool callback
curl -sG http://127.0.0.1:8765/api/enforcement-demo \
  --data-urlencode 'urn=urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)' \
  | python3 -m json.tool
```

The UI buttons **Scan connected DataHub** and **Prove tool gate** call these
same endpoints. A scan keeps the selected decision visible while it runs;
blocked actions are reported as `tool_not_invoked`, not as a simulated success.

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
export METAGATE_LIVE_DATAHUB_URN="urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)"
PYTHONPATH=src python3 -m unittest tests.test_datahub_schema -v
```

The live test is skipped when `DATAHUB_GRAPHQL_URL` or
`METAGATE_LIVE_DATAHUB_URN` is absent. Run it with the local DataHub
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
- Local API-backed MetaGate Review app
- Packaged browser extension that detects DataHub asset URNs
- MCP server and DataHub Skill-compatible entrypoint for agent integrations
- Dockerized review API path
- Safe write-back payloads and receipts
- Installed commands: `metagate`, `metagate-review`, `metagate-mcp`, and
  `metagate-doctor`
- Tests, curated benchmark, contribution guide, release notes, and docs

For a single local check, run `./scripts/verify_metagate.sh`. It runs the
tests, rebuilds the extension package, and reports whether DataHub and the
review API are reachable.

For a judge-ready release snapshot, run:

```bash
./scripts/judge_proof.sh
```

This writes a machine-readable proof bundle to `/tmp/metagate-release-proof.json`.
It records the commit, test count, curated benchmark, four-action enforcement
story, extension package, local prerequisite status, and any external proof
that still requires a real deployment or human reviewer. It never labels an
unconfigured MCP server, live write-back, or independent review as complete.

Deployment-specific proof:

- The browser extension is packaged and installable; native DataHub frontend
  registration still depends on the target deployment's extension mechanism.
- The public hosted page uses sanitized data, not a public DataHub deployment.
- Live write-back is implemented as a mutation-plus-read-back adapter, but a
  real DataHub screenshot requires an approved mutation and credentials for a
  reachable deployment.
- A blank independent-label template and scorer are included. The informal
  sanity labels are not presented as independent benchmark evidence.

## Core Capabilities

- Evidence extraction for ownership, glossary, lineage, assertions, incidents,
  freshness, usage, and policy
- Capability-based certification
- Readiness and confidence scoring
- MetaGate Certificate output
- Gap classification: missing, stale, incomplete, contradictory
- Remediation planning
- Policy simulation
- Readiness diffs and trust timeline
- Audit logging
- YAML policy profiles

## Security Model

MetaGate is designed to be safe by default:

- read-only evaluation unless write-back mutations are explicitly configured
- DataHub token stays server-side in local/private deployments
- public demo uses sanitized fixture data, never a private DataHub token
- write-back is deployment-owned and gated by approved GraphQL mutation documents
- recommended production flow separates requester, reviewer, and metadata owner

## SDK

```python
from metagate import ReadinessEngine, load_policy
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
