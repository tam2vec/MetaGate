# Official DataHub MCP proof

**Status:** VERIFIED locally, read-only

- **Server:** official `mcp-server-datahub` 3.4.6 over stdio
- **DataHub:** local GMS at `http://localhost:8080`
- **Asset:** `SampleHiveDataset`
- **Trace:** `initialize` → `tools/list` → `get_entities` → `get_dataset_queries`
- **Returned context:** two owners, schema fields, zero assertions, zero open incidents, and three dataset queries

The full machine-readable trace is in [`official-datahub-mcp-proof.json`](official-datahub-mcp-proof.json). This proves the official integration path was run locally; it does not claim a public or production MCP deployment. Fields unavailable from the MCP response remain unavailable.
