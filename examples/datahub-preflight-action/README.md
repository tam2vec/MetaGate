# Context Gradient Preflight

This folder sketches the native DataHub action/plugin path.

In the hackathon repo, the product is named Predicate. The production action can
be presented as **Context Gradient Preflight**: a DataHub-native gate that
checks whether a dataset is ready for AI use.

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

> Context Gradient Preflight is the intended native DataHub action. The
> hackathon proof uses the same contract through the CLI, local review API, and
> browser extension prototype.

Avoid:

> This repo already ships a packaged production DataHub plugin.
