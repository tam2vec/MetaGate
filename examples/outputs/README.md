# Representative Outputs

These files are captured from the bundled local DataHub-shaped fixture. They
show the shape of the user-facing artifacts without claiming live DataHub
validation.

- `certificate.json`: MetaGate Certificate summary.
- `action-metagate.json`: Go/no-go metagate for a risky AI action.
- `allowed-action.json`: Representative bundled-fixture allowed decision.
- `blocked-action.json`: Representative bundled-fixture blocked decision.
- `live-datahub-proof.html`: Visual proof page for the local validation fixture.
- `metagate-demo-app.html`: Interactive local demo for asset/capability decisions.
- `live-datahub-proof.md`: Markdown summary of the local validation fixture.
- `live-datahub-proof.json`: Machine-readable summary of the local validation fixture.
- `before-after-repair.json`: Before/after metadata repair proof artifact.
- `writeback-proof.json`: Safe write-back proof and payload shape.
- `writeback-receipt.json`: safe local receipt showing what would be written
  when deployment-specific mutations are configured.
- `context-contract.json`: machine-readable agent permissions.
- `explainability-report.json`: evidence-to-policy-to-decision explanation.
- `blocked-action.json`: deterministic admission result for a risky action.
- `readiness-diff.json`: before/after capability change after metadata repair.
- `policy-simulation.json`: comparison of current and proposed policy outcomes.
- `writeback-payload.json`: representative DataHub write-back body.

Run the live validation documented in `docs/live-datahub-validation.md` before
presenting these as deployment evidence.
