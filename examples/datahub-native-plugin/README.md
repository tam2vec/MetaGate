# MetaGate Preflight Action

This is the native integration boundary for deployments that can register a
DataHub Action, webhook, or private frontend action. The event payload is:

```json
{"entityUrn":"urn:li:dataset:(urn:li:dataPlatform:hive,example,PROD)","capability":"answer-business-questions"}
```

The working handler is `metagate.preflight`. It evaluates the live DataHub
metadata, returns a versioned constraint contract, and fails closed for a
blocked request. A tool runner must call
`metagate.agent_gate.guarded_tool_call` before invoking an agent tool.

`handler.py` is the runnable deployment bridge. It reads one JSON event from
stdin and POSTs it to MetaGate's guarded `/api/datahub-action` endpoint. A
connection or configuration failure returns `blocked`; it never forwards raw
rows.

## Local proof

Start MetaGate Review, then post the same payload to:

```text
POST http://127.0.0.1:8765/api/datahub-action
```

Use `registration.example.yml` as the deployment registration template. The
exact registration screen differs by DataHub version, so this folder does not
pretend to be an in-core DataHub plugin package.

## Package the adapter

From the repository root:

```bash
PYTHONPATH=src python3 scripts/package_native_plugin.py
```

This creates `dist/metagate-datahub-preflight-adapter.zip`. It contains the
runnable bridge, manifest, registration template, and deployment notes. A
DataHub operator must still register the endpoint through the Action or webhook
mechanism supported by that deployment; the bundle cannot install itself into
DataHub Core.
