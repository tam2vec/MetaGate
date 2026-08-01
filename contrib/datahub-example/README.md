# DataHub Example Contribution

This folder is an upstream-ready, dependency-light example contribution. It
demonstrates how DataHub metadata can be converted into a deterministic
AI-readiness certificate without changing DataHub core.

## Proposed upstream shape

1. Add the example policy and evidence model documentation.
2. Add the Skill manifest and reference entrypoint.
3. Keep deployment-specific GraphQL mutations outside the example.
4. Link to the reusable SDK for teams that need continuous certification.

## Acceptance checklist

- [ ] Run the example against a supported DataHub version.
- [ ] Confirm GraphQL field names for that version.
- [ ] Confirm the preferred write-back target with DataHub maintainers.
- [ ] Attach CI output and a short demo recording to the pull request.
