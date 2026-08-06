# Predicate MCP integration

Predicate exposes three MCP tools over stdio:

- `predicate_evaluate`: return allow/block, scores, failed terms, and evidence
- `predicate_constraint_contract`: return the agent boundary: allowed action,
  forbidden actions, required approval, permitted scope, and decision ID
- `predicate_evidence`: return the evidence facts and gaps behind a decision

This lets an agent call Predicate directly instead of running a shell command.
The server keeps `DATAHUB_TOKEN` in its process and never returns it to the
agent. It reads DataHub through the same GraphQL adapter used by the CLI and
review API, so all three paths share one evaluator.

## Install and run

From the repository root:

```bash
python3 -m pip install -e ".[datahub]"
export DATAHUB_GRAPHQL_URL="http://localhost:8080/api/graphql"
export DATAHUB_TOKEN="<read-only-token-if-required>"
predicate-mcp \
  --policy examples/policies/enterprise_ai.yml \
  --datahub-url "$DATAHUB_GRAPHQL_URL"
```

For an MCP client, copy the settings in `predicate-mcp.json` and change the
working directory to the cloned repository if the client needs an absolute
command path. The server is intentionally read-only. Write-back remains a
separate, explicit, verified command.

## Smoke test

The repository test starts the stdio server, performs `initialize` and
`tools/list`, and checks that all three tools are advertised without contacting a
real DataHub. A real evaluation still requires a reachable GraphQL endpoint.

## Compose with DataHub's official MCP server

Predicate is the final gate, not a replacement for DataHub's own agent tools.
In an agent session, register the official [DataHub MCP Server](https://github.com/acryldata/mcp-server-datahub)
alongside Predicate MCP:

1. Ask DataHub MCP to search or inspect the asset and resolve its dataset URN.
2. Pass that exact URN to `predicate_evaluate` or
   `predicate_constraint_contract`.
3. Give the agent only the returned `allowed_action`, `forbidden_actions`,
   permitted scope, and exact evidence.
4. Stop the workflow when Predicate returns `blocked`; do not treat a score as
   permission to continue.

This keeps DataHub's official search/context capabilities in the loop while
adding Predicate's action-specific admission boundary. The two servers are
registered separately because their installation and tool names are owned by
their respective projects.

## Verify the official DataHub MCP process

Predicate can run a short, read-only integration probe against the separately
installed official server. This is optional and has no network side effect
until you configure the command:

```bash
export DATAHUB_GRAPHQL_URL="http://localhost:8080/api/graphql"
export DATAHUB_TOKEN="<read-only-token-if-required>"
export PREDICATE_DATAHUB_MCP_COMMAND='npx -y @acryldata/mcp-server-datahub'
PYTHONPATH=src python3 scripts/probe_datahub_mcp.py \
  --urn "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)"
```

After installing the package, the equivalent console command is:

```bash
predicate-datahub-mcp-probe \
  --urn "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)"
```

The probe performs the MCP handshake, lists the official tools, and calls
`get_entities` for the URN. It then parses the returned structured content or
JSON text into Predicate evidence: owner, glossary, lineage, schema/column
coverage, latest assertion result, freshness, incidents, usage, and policy.
When the server exposes the optional `get_dataset_queries` tool, Predicate
makes a second read-only call and records only query count and latest timestamp;
it never returns query text.
An omitted field is reported as `unavailable`; an explicitly empty field is
reported as `absent`. It reports `verified` only when the requested asset was
actually returned; `not_configured` means the optional process was not
registered, and `attention_required` means the command, credentials, schema,
or server needs repair. DataHub's current official server and tool list are documented in the
[official repository](https://github.com/acryldata/mcp-server-datahub). Use
its setup flow, including `npx -y @acryldata/mcp-server-datahub init`, when
your MCP client needs a saved connection profile.
