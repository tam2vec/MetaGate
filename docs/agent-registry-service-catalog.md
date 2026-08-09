# MetaGate Agent Governance

MetaGate now treats the execution path as part of an AI-action decision:

```text
registered agent -> registered skill -> registered tool/API -> owning service -> dataset
```

For a risky action, the local Review API can fail closed unless every link in
that chain is registered, linked, and in scope. The verified chain is returned
in the decision contract and is enforced again by `metagate.agent_gate` before
the callable tool runs. A browser panel or a green score cannot bypass that
check.

## What is included in this repository

- `src/metagate/agent_registry.py` verifies the chain and produces evidence.
- `examples/data/agent_registry.json` is a DataHub-shaped local catalog for the
  reproducible OSS demo.
- `--require-agent-registry` makes the decision fail closed when the chain is
  missing, mismatched, or unreadable.
- `/api/status` reports the registry configuration.
- `/api/integration-proof` shows the agent, skill, tool, and service chain.
- `/api/tool-call` rejects calls outside the verified contract before invoking
  the callable.

Start the local proof with:

```bash
export METAGATE_REQUIRE_AGENT_REGISTRY=1
./scripts/start_metagate_review.sh
```

The page's **Agent integration proof** panel should show the four registered
URNs and a verified chain. To demonstrate fail-closed behavior, change one ID
or remove one link from the local JSON, restart the server, and request an
action. MetaGate should show the exact broken link and `/api/tool-call` should
reject the call.

## DataHub mapping

DataHub's Agent Registry models APIs/tools, skills, and agents. DataHub's
Service Catalog models the service and the API endpoints it owns. MetaGate's
local JSON is an adapter for the same relationship vocabulary so the demo is
reproducible without pretending that a local fixture is a hosted DataHub Cloud
registry.

For a real DataHub deployment, register the same entities and relationships in
that deployment, then point MetaGate at the deployment-specific read API and
use the returned URNs in `METAGATE_AGENT_ID`, `METAGATE_SKILL_ID`,
`METAGATE_TOOL_ID`, and `METAGATE_SERVICE_ID`. Keep the local catalog for
offline tests; do not present it as a production DataHub registration.

Official references:

- [DataHub Agent Registry tutorial](https://docs.datahub.com/docs/api/tutorials/agent-registry/)
- [DataHub Service Catalog tutorial](https://docs.datahub.com/docs/api/tutorials/service-catalog)
