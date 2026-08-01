# Production Gap Closure

This document tracks the biggest remaining gaps and the strongest artifact now
included for each one.

| Gap | Status after this pass | Demo claim |
| --- | --- | --- |
| Packaged DataHub plugin | Browser extension prototype plus DataHub panel contract exist. A production plugin is still future work. | "The automatic UX is proven through a browser extension prototype; DataHub packaging is the next integration step." |
| Public live demo | Dockerfile and local API server exist. Public Netlify remains static because private DataHub tokens should not be exposed. | "Hosted page is sanitized. Live proof runs locally or in a private deployment." |
| Live write-back screenshot | Safe payloads, receipts, and mutation-gated adapter exist. A real DataHub screenshot still needs a deployment-supported mutation. | "Read-only by default; write-back is explicit and deployment-owned." |
| Independent benchmark | CSV template and scorer exist. External labels are still needed from reviewers. | "Curated benchmark passes; independent agreement can be computed once reviewers label cases." |
| Real enterprise data | Local DataHub sample and hard finance fixture exist. A customer/private enterprise dataset is still external. | "No customer data is required for the public demo; production validation should run on private assets." |
| Install friction | Package entrypoint, Dockerfile, browser extension README, and runbooks exist. | "The demo can be run with local DataHub plus one Predicate server command." |
| Scoring calibration | Scoring docs exist. Calibration still needs independent labeled data. | "Weights are policy-configurable and not claimed as universal accuracy." |
| Security story | Security policy and write-back safety docs exist. Production RBAC/token controls must be configured by deployment. | "Predicate can be read-only, uses DataHub auth token, and gates mutation write-back." |

## Remaining External Tasks

1. Ask 1-2 reviewers to label the independent benchmark CSV.
2. Capture the browser extension running on the local DataHub page.
3. Capture one terminal/API proof for the same URN shown in DataHub.
4. Capture live write-back only if a non-production DataHub mutation is known to
   work in the target deployment.
5. Deploy the Dockerized review API only behind a private network or with a
   non-sensitive demo DataHub endpoint.
