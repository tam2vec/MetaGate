# Production Gap Closure

This document tracks the biggest remaining gaps and the strongest artifact now
included for each one.

| Gap | Status after this pass | Demo claim |
| --- | --- | --- |
| Packaged DataHub plugin | Browser extension prototype, DataHub panel contract, automatic URN-detection flow, screenshot checklist, and Predicate Preflight action contract exist. A production DataHub package is still future work. | "The automatic UX is proven through a browser extension prototype; DataHub packaging is the next integration step." |
| Public API fixture demo | Public Netlify page can call the Render API at `https://predicate-ixz0.onrender.com` using sanitized fixture data. The page now labels this as fixture-backed, not a public DataHub deployment. | "Hosted page is API-backed with sanitized fixture data. Real DataHub proof runs locally or in a private deployment." |
| Live write-back screenshot | Safe payloads, receipt command, receipt file, UI write-back queue, Context Contract custom aspect shape, and mutation-gated adapter exist. A real DataHub UI mutation still needs a deployment-supported mutation. | "Read-only by default; write-back is explicit and deployment-owned." |
| Independent benchmark | Two reviewers labeled 10 demo decisions with 10/10 agreement. CSV template, scorer, protocol, reviewer request, and unsafe-answer reduction benchmark framing are included. More labels are still needed before any production claim. | "Curated benchmark passes; early external agreement exists on 10 demo labels; this is not a production accuracy claim." |
| Real enterprise data | Local DataHub sample, hard finance fixture, and private deployment adapter docs exist. A customer/private enterprise dataset is still external. | "No customer data is required for the public demo; production validation should run on private assets." |
| Install friction | Package entrypoints, `predicate`, `predicate-review`, Dockerfile, browser extension README, and runbooks exist. | "The demo can be run with local DataHub plus one Predicate server command." |
| Scoring calibration | Scoring docs exist. Calibration still needs independent labeled data. | "Weights are policy-configurable and not claimed as universal accuracy." |
| Security story | Security policy, write-back safety docs, UI Security & RBAC panel, and RBAC enforcement model exist. Production RBAC/token controls must be configured by deployment. | "Predicate can be read-only, uses DataHub auth token server-side, and gates mutation write-back." |
| Runtime readiness | Health endpoints, startup validation, Docker healthcheck, Render health check, and fail-closed mode exist. | "Predicate has production-oriented runtime controls, while deployment hardening remains environment-specific." |
| Remediation depth | Public review app now shows asset-specific repair steps, approved glossary suggestions, concrete assertions, owner actions, and rerun expectations. | "Predicate returns a repair plan, not just a blocked decision." |
| Trust lifecycle | Public review app now shows a trust timeline for evidence change, policy check, trust revocation or certification, repair, and rerun. | "Predicate is continuous control, not a one-time score." |

## Remaining External Tasks

1. Ask 1-2 reviewers to label the independent benchmark CSV using
   `docs/external-benchmark-request.md`.
2. Capture the browser extension running on the local DataHub page.
3. Capture one terminal/API proof for the same URN shown in DataHub.
4. Capture live write-back only if a non-production DataHub mutation is known to
   work in the target deployment.
5. Keep the public Render API on sanitized fixture data unless a non-sensitive
   demo DataHub endpoint is available.
