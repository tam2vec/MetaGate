# MetaGate DataHub Hackathon Video Script

Target length: 3 minutes 30 seconds.

## The one-line story

> **DataHub gives AI context. MetaGate gives AI permission.**

The video should feel like one reveal: open a DataHub asset, see MetaGate
appear beside it, ask for an AI action, watch the evidence-backed block, fix the
gap, and prove that the protected tool never runs without permission.

## Recording setup

Have these ready:

1. Local DataHub v1.7.0 at `http://localhost:9002`.
2. MetaGate Review at `http://127.0.0.1:8765/review`.
3. Chrome with the unpacked extension loaded from `examples/browser-extension`.
4. A DataHub page for `fct_users_created`.
5. The bundled fixture demo on port `8766` for the positive control.
6. A terminal only for the final proof backup.

Before recording, run:

```bash
metagate-doctor
PYTHONPATH=src python3 -m unittest discover -s tests -q
```

The live review scans the connected catalog (currently 74 datasets). Keep the
six-asset fixture available only as a clearly labelled rehearsal fallback.

Never show tokens, private URLs, or customer data. Do not claim that the
Chrome extension is a native DataHub plugin, that the official DataHub MCP ran,
or that a public deployment is connected unless that is separately verified.

## 0:00–0:18 — The hook

Screen: a normal DataHub dataset page.

Say:

> DataHub already knows what this dataset means, who owns it, how it was
> produced, whether its checks pass, and whether it is fresh. But an AI agent
> still needs a sharper answer: may I act on it right now?

Pause briefly, then say:

> MetaGate is the missing permission layer.

## 0:18–0:48 — The Chrome extension reveal

Screen: refresh the DataHub asset page with the MetaGate extension enabled.

Show the injected panel on the right with the asset name, decision, readiness,
confidence, and compact repair plan.

Say:

> I did not copy this URN into a separate tool. The browser extension reads the
> DataHub asset page I am already viewing, sends that exact URN to MetaGate, and
> puts the action decision back in context.

Point to the compact repair plan:

> This is the first useful difference: the catalog remains the source of
> context, while MetaGate adds a decision about what an agent may do.

On-screen label: `Chrome extension prototype · local DataHub · local MetaGate API`.

## 0:48–1:18 — The block is evidence-backed

Screen: open MetaGate Review with `fct_users_created` selected and
`Autonomous agent action` requested.

Say:

> Now I will ask for a higher-risk capability. MetaGate does not answer with a
> generic data-quality score. It checks this action against this asset's current
> evidence.

Show the evidence-first card and point to:

- the exact DataHub identity;
- `BLOCKED`;
- the missing assertion and lineage evidence;
- readiness and confidence thresholds;
- the source and current catalog scope.

Say:

> The block is explainable: the agent is missing the evidence required for this
> action. No evidence, no autonomous action.

## 1:18–1:48 — Turn the block into a repair

Screen: click **Repair plan** and then **Copy full plan**.

Say:

> A block is only useful if somebody can fix it. MetaGate converts each
> blocking term into a precise steward step: add dataset-specific assertions,
> complete the expected lineage, then rerun the same asset and capability after
> DataHub indexing.

Briefly show that the copied plan contains:

- exact URN;
- requested capability;
- decision before repair;
- blocking evidence;
- copyable repair values or explicit placeholders;
- the final verification command.

Say:

> MetaGate proposes the repair. It does not silently mutate DataHub.

## 1:48–2:15 — Show a truthful positive control

The current connected DataHub catalog is a blocked-first run: its available
GraphQL evidence does not currently produce an allowed high-risk action. Do not
select `SampleHiveDataset` and call it live-allowed.

Start the clearly labelled fixture demo on port `8766`:

```bash
METAGATE_PORT=8766 ./scripts/start_metagate_demo.sh
```

Screen: `http://127.0.0.1:8766/review`, with the source label visible. Select
`analytics.revenue_daily` and the same capability.

Say:

> For a positive control, I am switching to MetaGate's bundled DataHub-shaped
> fixture. This asset is intentionally complete, so the same policy returns
> allowed. The fixture label is visible: this demonstrates the decision
> contract, not live DataHub health.

Point to the allowed decision and evidence facts:

> This is why MetaGate is not a blanket deny-list. A complete evidence set can
> pass; the current live catalog remains blocked until its missing evidence is
> actually available.

## 2:10–2:35 — Prove the boundary

Screen: **Proof & audit** → constraint contract and enforcement result.

Say:

> The decision is not just a badge in a dashboard. At the tool boundary, a
> blocked contract fails closed and the protected callback is not invoked.

Show `tool_not_invoked` or the equivalent blocked enforcement result.

Say:

> The agent sees a machine-readable contract; the human sees the reason and the
> repair path.

## 2:35–2:58 — Show the connected system

Screen: Proof & audit, then the DataHub property or local receipt if already
verified.

Say:

> MetaGate also carries the decision through the governed execution chain:
> agent, skill, tool, and owning service. In this local environment, the
> Context Contract write-back and read-back were verified locally for
> SampleHiveDataset.

Use the precise label `verified-local-rest` if showing that receipt. Do not
imply that every deployment supports the same mutation.

## 2:58–3:15 — Explain the scope and boundaries

Screen: Review status/source labels.

Say:

> This live local run reads the connected DataHub catalog and currently scans 74
> datasets. In this recording, the live high-risk result is blocked because the
> required evidence is not available from the current GraphQL response. The
> positive contrast is explicitly labelled fixture evidence. Native deployment plugins, a public live DataHub, the
> separately configured official MCP server, independent reviewers, and an
> upstream merge remain external dependencies.

This short honesty moment increases trust; keep it to one sentence per label.

## 3:15–3:30 — The close

Screen: MetaGate Review beside the DataHub asset page, or README closing frame.

Say:

> DataHub already has the context. MetaGate turns that context into permission:
> check the evidence, allow or block the exact AI action, and give the owner a
> path to repair. Before AI acts, MetaGate checks the gate.

End on the words:

> **Context in DataHub. Permission in MetaGate.**

## Backup path

If the live DataHub or review API is unavailable, say:

> The live DataHub endpoint is unavailable in this recording, so I am switching
> to MetaGate's bundled DataHub-shaped fixture. This proves the engine and
> output contract; it is labelled fixture evidence, not a live catalog claim.

Run the fixture on another port:

```bash
PYTHONPATH=src python3 scripts/serve_review.py \
  --host 127.0.0.1 \
  --port 8766 \
  --policy examples/policies/enterprise_ai.yml \
  --datahub-file examples/data/six_asset_review_graph.json \
  --no-recorded-fallback
```

If the extension is unavailable, show the DataHub Embed prototype or the full
Review page, and describe the browser panel as a packaged prototype rather
than pretending it is present.

## Claims to avoid

- “MetaGate has installed a native DataHub plugin.”
- “The public demo is connected to our private local DataHub.”
- “The Chrome extension is deployed inside every DataHub instance.”
- “The official DataHub MCP ran” when it is not configured and verified.
- “The benchmark proves production accuracy.”
- “The repair loop mutated DataHub” when showing a proposal or fixture.
- “All 74 datasets are production-ready.”
