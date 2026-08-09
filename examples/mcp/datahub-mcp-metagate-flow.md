# DataHub MCP + MetaGate flow

This is the judge-facing integration story:

```text
DataHub MCP search/get context
          |
          v
dataset URN + current DataHub context
          |
          v
MetaGate MCP metagate_constraint_contract
          |
          +--> allowed action + permitted scope
          +--> blocked action + exact repair reason
```

## Agent contract

Use the official DataHub MCP server for discovery and context, then call
MetaGate with the resolved URN:

```json
{
  "name": "metagate_constraint_contract",
  "arguments": {
    "urn": "<URN returned by DataHub MCP>",
    "capability": "generate-executive-metrics"
  }
}
```

MetaGate re-reads current evidence through the same GraphQL adapter used by
the CLI and Review API. It returns latest assertion results, freshness,
incidents, lineage coverage, ownership, unavailable signals, a decision ID,
and the actions the agent must not perform.

Do not copy the DataHub token into the browser or public demo. Keep both MCP
servers on the private agent side.
