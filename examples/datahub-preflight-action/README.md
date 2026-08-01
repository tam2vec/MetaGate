# Predicate Preflight

This folder sketches the native DataHub action/plugin path.

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

## Production Claim

Use:

> Predicate Preflight is the intended native DataHub action. The
> hackathon proof uses the same contract through the CLI, local review API, and
> browser extension prototype.

Avoid:

> This repo already ships a packaged production DataHub plugin.
