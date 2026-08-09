# Future Work

These are the remaining improvements that would move MetaGate from a strong
hackathon MVP toward a production-ready product.

## Product UI

- Turn the `examples/datahub-embed/` prototype into a packaged DataHub frontend
  extension or approved internal DataHub customization.
- Replace the static `examples/outputs/metagate-demo-app.html` data with a
  hosted service that calls MetaGate live.
- Add authenticated deep links from each result back to the exact DataHub asset
  page.

## DataHub write-back proof

- Configure a deployment-supported GraphQL mutation for
  `DATAHUB_CERTIFICATE_MUTATION`.
- Write the MetaGate Certificate back to a non-production DataHub asset.
- Capture before/after screenshots showing the certificate or custom property in
  DataHub.
- Keep write-back disabled by default for read-only safety.

## Broader live validation

- Run MetaGate against 20-30 real DataHub assets from multiple platforms.
- Record asset URN, capability, decision, reason, and metadata gap for each run.
- Keep production accuracy claims out until labels are independently reviewed.

## Package rename

- The public project name is MetaGate, but the internal Python package remains
  `context_gradient` for compatibility with the original MVP.
- A full package migration can rename imports to `metagate` after the demo, with
  compatibility shims for existing users.

## Hosted demo

- Publish the visual proof page with GitHub Pages or another static host.
- Link the hosted proof page from Devpost and the README.

## Independent validation

- Have data stewards label a held-out set that was not used while tuning the
  policies.
- Report precision/recall only after that independent label set exists.
