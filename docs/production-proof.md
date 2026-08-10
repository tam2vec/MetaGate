# Production Proof Runbook

MetaGate has two layers: the decision engine is usable locally today, while a
few deployment steps require an administrator or a DataHub maintainer. This
runbook keeps those boundaries visible.

## The end-to-end story

1. DataHub exposes an asset and its current metadata.
2. MetaGate evaluates the requested action against an action-specific profile.
3. MetaGate returns evidence states, not just a score: present, absent, stale,
   or unavailable.
4. The agent receives a constraint contract. A blocked contract causes the
   `/api/tool-call` endpoint to return HTTP 403 and the tool callback is never
   invoked.
5. A repair changes the exact failed fact.
6. MetaGate polls until the repaired metadata is readable, evaluates again,
   and stores before/after audit events.

## Run the local proof

Start DataHub and load the provided metadata:

```bash
datahub docker quickstart
datahub datapack load showcase-ecommerce --force
```

Start MetaGate against the local GraphQL endpoint:

```bash
export DATAHUB_GRAPHQL_URL="http://localhost:8080/api/graphql"
./scripts/start_metagate_review.sh
```

Open `http://127.0.0.1:8765/review`. The first screen shows the current
decision and evidence. Scores are secondary. The configured scope can be
expanded with `METAGATE_DISCOVER_ASSETS=1` to score the datasets currently
present in the connected DataHub.

## Prove the tool boundary

Use a blocked asset. The response is intentionally HTTP 403 and includes
`"enforcement": "tool_not_invoked"`:

```bash
curl -sS -X POST http://127.0.0.1:8765/api/tool-call \
  -H 'Content-Type: application/json' \
  --data '{"dataset_urn":"urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)","action":"autonomous-agent-action"}'
```

Use a fully evidenced allowed fixture to see the permitted callback path:

```bash
curl -sS -X POST http://127.0.0.1:8765/api/tool-call \
  -H 'Content-Type: application/json' \
  --data '{"dataset_urn":"urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)","action":"autonomous-agent-action"}'
```

This demo callback is deliberately harmless. In a real agent, replace it with
the actual tool invocation only after checking the returned contract.

## Show the repair loop

The visible repair panel is a deterministic fixture proof. It demonstrates the
control flow without pretending that a mutation happened in a customer
DataHub:

```bash
PYTHONPATH=src python3 scripts/run_repair_loop_demo.py --json
```

It records: blocked before state, exact repair, indexing poll, allowed/changed
after state, score delta, and audit event sequence. The browser labels this
`Simulated proof` until a real deployment mutation is configured.

## Verify a real local DataHub write-back

Only run this against a disposable local deployment or a dataset for which you
have explicit write permission. The default mode remains read-only.

```bash
export DATAHUB_GMS_URL="http://localhost:8080"
export DATAHUB_TOKEN="<authorized-token-if-your-deployment-requires-one>"

PYTHONPATH=src python3 scripts/writeback_datahub.py \
  "urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)" \
  --policy examples/policies/enterprise_ai.yml \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --datahub-gms-url "$DATAHUB_GMS_URL" \
  --transport rest --yes
```

The command must print a read-back verification. Capture the receipt and the
same property in the DataHub dataset UI. If the deployment does not support
the property endpoint, configure its approved mutation and verification query:

```bash
export DATAHUB_CERTIFICATE_MUTATION="<deployment-approved GraphQL mutation>"
export DATAHUB_CERTIFICATE_QUERY="<deployment-approved GraphQL read-back query>"
```

Do not claim write-back is verified until both the command receipt and DataHub
UI show the same decision ID and timestamp.

## Show the official DataHub MCP call

MetaGate does not invent an MCP command because DataHub deployments expose
different transports. Configure the official DataHub MCP server command from
the [DataHub MCP repository](https://github.com/acryldata/mcp-server-datahub),
then set:

```bash
export METAGATE_DATAHUB_MCP_COMMAND="<your approved DataHub MCP command>"
```

The review page will show the sanitized tool trace only after the command
returns successfully. Until then it says `not configured`, rather than
claiming that an MCP call occurred.

For this repository, the official path has been verified locally against
`SampleHiveDataset` with `uvx mcp-server-datahub@latest --transport stdio`.
See the saved [proof summary](../examples/outputs/official-datahub-mcp-proof.md)
and [JSON output](../examples/outputs/official-datahub-mcp-proof.json). A fresh
deployment still needs its own configured command and credentials.

## Adversarial scenarios and human labels

Generate the scenario set:

```bash
PYTHONPATH=src python3 scripts/generate_adversarial_scenarios.py
```

This produces 60 synthetic cases across prompt injection, restricted columns,
stale metadata, failed assertions, conflicting owners, tool failures,
unavailable evidence, lineage breaks, freshness breaches, incidents, policy
mismatches, and unsafe mutations. These are test scenarios, not independent
accuracy evidence. Use the blank reviewer template in
`examples/benchmark/independent-label-template.csv`; never fill reviewer
answers on their behalf.

## Native DataHub integration boundary

`examples/datahub-native-plugin/` contains the action contract and registration
shape. Installing it into a real DataHub requires the deployment's supported
action/frontend extension mechanism and an administrator. The repository can
provide the contract and adapter, but cannot truthfully claim that it is
installed in every DataHub deployment.

## What is still external

- A maintainer must approve and merge the prepared contribution in
  `datahub-project/datahub-skills`.
- A DataHub administrator must provide an authorized mutation or token for
  verified write-back.
- Independent reviewers must label the benchmark cases.
- A public live DataHub requires a reachable, permissioned deployment; never
  expose localhost or a private token through Netlify.
