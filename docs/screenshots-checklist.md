# MetaGate Video and Screenshot Checklist

The strongest visual sequence is:

> **DataHub asset → Chrome decision panel → MetaGate evidence → repair plan →
> allowed contrast → fail-closed proof.**

Take live/local screenshots first. Put fixture screenshots in a separate
folder and label them `fixture demo` or `rehearsal artifact`.

## Must-have captures

| Order | Capture | What it proves | Suggested filename |
| ---: | --- | --- | --- |
| 1 | DataHub `fct_users_created` page with the exact URN visible | The starting catalog context is identifiable | `01-datahub-fct-users-created.png` |
| 2 | Chrome extension panel injected beside that same DataHub page | MetaGate can evaluate the asset a user is already viewing | `02-chrome-metagate-panel-blocked.png` |
| 3 | MetaGate Review connection/source/scope labels | The decision is tied to the intended local DataHub source | `03-metagate-local-scope-74.png` |
| 4 | Evidence-first `BLOCKED` card | A capability-specific action is denied from current evidence | `04-metagate-blocked-evidence.png` |
| 5 | Full Repair plan | Missing evidence becomes precise steward work | `05-metagate-repair-plan.png` |
| 6 | Copied repair plan or verification command | The plan preserves the URN, capability, gaps, and re-check | `06-metagate-copied-plan.png` |
| 7 | Fixture demo: `analytics.revenue_daily` with `ALLOWED` and the fixture label visible | A complete positive control exists without misrepresenting the live catalog | `07-metagate-fixture-allowed-contrast.png` |
| 8 | Proof & audit constraint contract | The decision becomes a machine-readable boundary | `08-metagate-constraint-contract.png` |
| 9 | Blocked enforcement response with `tool_not_invoked` | The protected callback is not invoked | `09-metagate-fail-closed.png` |
| 10 | Verified local write-back/read-back receipt, if shown | The Context Contract path was verified for the named local asset | `10-metagate-local-writeback-receipt.png` |
| 11 | Tests and benchmark output | Local engineering checks pass without implying production accuracy | `11-metagate-tests.png` |

## Chrome extension screenshot rules

The extension frame should show:

- the DataHub URL bar or page identity with the dataset URN;
- the normal DataHub asset page still visible;
- the MetaGate panel injected on the right;
- the decision, readiness, confidence, and repair queue;
- the label that this is a local MetaGate API and extension prototype;
- no private token, cookie, customer data, or unrelated browser tabs.

This is the video's “oh wow” frame: the decision appears where the data work is
already happening.

## Optional comparison frames

Capture these only if they are clean and truthful:

1. Chrome panel for the blocked asset.
2. Chrome panel for an allowed asset.
3. MetaGate Review for the same two assets under the same capability.
4. **Policy tests** showing the conformance suite.
5. **Proof & audit** showing Agent, Skill, Tool, and Service registration.
6. **Changes** showing the verified local Context Contract property.

## Before/after repair evidence

Capture this sequence only when the metadata change and read-back are actually
verified:

1. DataHub asset before repair.
2. The exact owner, glossary, lineage, assertion, or freshness change.
3. DataHub indexing/event timestamp.
4. MetaGate after-check for the same URN and capability.
5. Readiness/capability diff.
6. DataHub write-back property or receipt, with secrets redacted.

If the repair is simulated or fixture-backed, label it `simulation` and say it
demonstrates sequencing only.

## Presentation rules

- Keep the exact URN visible in the DataHub, extension, MetaGate, and repair-plan
  frames.
- Show the decision and evidence state before showing a score.
- Keep source, mode, build, and scope labels in frame when they establish live
  versus fixture evidence.
- Use one blocked asset, one allowed asset, and one stress case at most.
- Do not use a screenshot of a proposed native plugin, external reviewer label,
  public deployment, or upstream PR as proof that it is shipped.
- Redact tokens, credentials, private hostnames, personal data, and customer
  identifiers.
