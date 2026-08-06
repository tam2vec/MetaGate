# Predicate Preflight

This folder defines the native DataHub action/plugin contract and the
deployment-specific write-back boundary.

Predicate Preflight is the intended DataHub-native gate: it checks whether a
dataset is ready for a specific AI use before the workflow proceeds.

## User Flow

1. User opens a DataHub dataset.
2. User clicks **Request AI Readiness**.
3. DataHub sends the dataset URN and requested AI capability to Predicate.
4. Predicate evaluates metadata readiness.
5. Predicate returns a Context Contract.
6. DataHub writes or displays the result as an assertion, custom aspect, or
   dataset panel.

## Files

- `action-contract.json`: request/response contract.
- `context-contract-aspect.json`: custom aspect shape for DataHub write-back.
- `writeback-mutation.example.graphql`: deployment-specific mutation template.
- `verify-contract.example.graphql`: read-after-write verification template.

The working command is `scripts/writeback_datahub.py`. By default it uses
DataHub's Python REST SDK to write the contract into the dataset's
`DatasetProperties.customProperties` under `predicate.ai_context_contract`,
then polls and compares the exact JSON on read-back. It refuses to report
success unless the contract can be read back from DataHub. Use `--transport
graphql` only when your deployment has an approved mutation and verification
query that are known to work.

## What is packaged today

The working, installable integration is the browser extension in
`examples/browser-extension`, plus the MCP server exposed by `predicate-mcp`.
These files make a native DataHub action implementable without pretending
that one universal mutation or frontend plugin API exists across deployments.

## Production Claim

Use:

> Predicate Preflight is the native DataHub action contract. The hackathon
> proof runs the same contract through the CLI, MCP server, local review API,
> and packaged browser extension. A deployment owner supplies the final native
> action registration and approved mutation document.

Avoid:

> This repo already ships a packaged production DataHub plugin.
