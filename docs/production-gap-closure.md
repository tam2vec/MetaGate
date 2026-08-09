# Production Gap Closure

This document tracks the biggest remaining gaps and the strongest artifact now
included for each one.

| Gap | Status after this pass | Demo claim |
| --- | --- | --- |
| Packaged DataHub integration | The browser extension is packaged by `scripts/package_extension.sh`; it detects the open DataHub URN and calls MetaGate automatically. The MCP server and native action contract are also included. Native DataHub frontend registration remains deployment-specific. | "The installable browser integration and agent tool are complete; native frontend registration uses the target deployment's extension mechanism." |
| Direct agent integration | `metagate-mcp` exposes `metagate_evaluate` and `metagate_evidence` over MCP, using the same GraphQL adapter as the CLI and review API. | "An agent can call MetaGate directly without shelling out." |
| Public API fixture demo | Public Netlify page can call the Render API at `https://metagate-ixz0.onrender.com` using sanitized fixture data. Live mode is implemented and fail-closed, but cannot be honestly enabled until Render has a reachable DataHub URL and token. | "Hosted page is API-backed and labels fixture mode; live DataHub mode is deployment-gated." |
| Live write-back screenshot | Safe payloads, receipt command, receipt file, UI write-back queue, Context Contract custom aspect shape, and mutation-gated adapter exist. A real DataHub UI mutation still needs a deployment-supported mutation. | "Read-only by default; write-back is explicit and deployment-owned." |
| Independent benchmark | The 30-case curated conformance suite, blank label template, scorer, protocol, reviewer request, and unsafe-answer reduction framing are included. The 10 informal sanity labels are not independent held-out evidence. | "MetaGate passes its curated checks; independent human validation is prepared but not yet completed." |
| Real enterprise data | Local DataHub sample, hard finance fixture, and private deployment adapter docs exist. A customer/private enterprise dataset is still external. | "No customer data is required for the public demo; production validation should run on private assets." |
| Install friction | Package entrypoints now include `metagate`, `metagate-review`, `metagate-mcp`, and `metagate-doctor`; `scripts/verify_metagate.sh` runs tests, rebuilds the extension ZIP, and checks prerequisites. | "The demo can be installed, checked, and run with explicit commands." |
| Scoring calibration | Scoring docs exist. Calibration still needs independent labeled data. | "Weights are policy-configurable and not claimed as universal accuracy." |
| Security story | Security policy, write-back safety docs, UI Security & RBAC panel, and RBAC enforcement model exist. Production RBAC/token controls must be configured by deployment. | "MetaGate can be read-only, uses DataHub auth token server-side, and gates mutation write-back." |
| Runtime readiness | Health endpoints, startup validation, Docker healthcheck, Render health check, and fail-closed mode exist. | "MetaGate has production-oriented runtime controls, while deployment hardening remains environment-specific." |
| Remediation depth | Public review app now shows asset-specific repair steps, approved glossary suggestions, concrete assertions, owner actions, and rerun expectations. | "MetaGate returns a repair plan, not just a blocked decision." |
| Trust lifecycle | Public review app now shows a trust timeline for evidence change, policy check, trust revocation or certification, repair, and rerun. | "MetaGate is continuous control, not a one-time score." |

## Remaining External Tasks

1. Ask 1-2 reviewers to label the independent benchmark CSV using
   `docs/external-benchmark-request.md`.
2. Open a pull request or issue against DataHub with a concrete documentation,
   schema, or integration improvement; a local contribution cannot be claimed
   as an upstream contribution until it is submitted there.
3. Capture the browser extension running on the local DataHub page.
4. Capture one terminal/API proof for the same URN shown in DataHub.
5. Capture live write-back only if a non-production DataHub mutation is known to
   work in the target deployment.
6. Keep the public Render API on sanitized fixture data unless a non-sensitive
   demo DataHub endpoint is available.
