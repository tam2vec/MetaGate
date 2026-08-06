# Hackathon DataHub Sources

Predicate can evaluate any dataset that exists in the connected DataHub. The
hackathon materials include these useful sources:

The links below are the official hackathon references. Predicate does not claim
that a scenario dataset is loaded until catalog discovery returns its real URN.

| Source | Best use | How Predicate uses it |
| --- | --- | --- |
| [`showcase-ecommerce`](https://docs.datahub.com/docs/quickstart) | Rich cross-platform graph with lineage, governance, glossary, and domains | Load it, then discover its real URNs |
| [`bootstrap`](https://docs.datahub.com/docs/quickstart) | Small starter graph for a quick smoke test | Load it, then discover its real URNs |
| [`nyc-taxi`](https://github.com/datahub-project/static-assets/tree/main/datasets/nyc-taxi) | Freshness and pipeline stress case | Follow the recipe, then discover its real URNs |
| [`healthcare`](https://github.com/datahub-project/static-assets/tree/main/datasets/healthcare) | Synthetic quality and sensitive-data scenario | Follow the recipe, then discover its real URNs |
| [`fiction-retail`](https://github.com/datahub-project/static-assets/tree/main/datasets/fiction-retail) | Clean multi-table analytics scenario | Follow the recipe, then discover its real URNs |

## Load the CLI Data Packs

With Docker and DataHub running:

```bash
datahub init
datahub datapack load showcase-ecommerce --force
datahub datapack load bootstrap --force
```

The `nyc-taxi`, `healthcare`, and `fiction-retail` entries are scenario
datasets, not guaranteed to be names accepted by `datahub datapack load` in
every CLI version. Use the load command shown on the corresponding hackathon
dataset page, then copy the resulting dataset URN from DataHub.

## Review Them in Predicate

Predicate's review page has a **Hackathon DataHub resources** section. Use
**Find loaded assets** to search the connected DataHub and show the actual
dataset URNs currently present. Select a discovered asset to evaluate it; the
score always comes from that asset's current metadata.

The **Check another DataHub asset** field is still available when you already
know a URN:

```text
urn:li:dataset:(urn:li:dataPlatform:<platform>,<name>,PROD)
```

After entering the URN, select **Check asset**. Predicate then reads the
current DataHub metadata and adds that result to the review page. It does not
invent a score for a pack that has not been loaded or for an asset whose URN
has not been provided.

The six-item dashboard is only the fallback fixture/demo set. In live mode,
Predicate discovers the current dataset URNs from DataHub on every refresh,
so loading a new pack does not require editing Python or adding a hard-coded
URN. Documentation links and dataset recipes are not scored themselves; a
dataset appears after its metadata has actually been loaded into DataHub.

## Official integration paths

Predicate's primary implementation is its live DataHub GraphQL adapter. The
hackathon paths it is designed to sit beside are:

- [DataHub Docs](https://docs.datahub.com/)
- [DataHub Skills](https://docs.datahub.com/docs/dev-guides/agent-context/skills)
- [Agent Context Kit](https://docs.datahub.com/docs/dev-guides/agent-context/agent-context)
- [DataHub MCP Server](https://github.com/acryldata/mcp-server-datahub)
- [Analytics Agent](https://docs.datahub.com/docs/features/feature-guides/analytics-agent)
- [DataHub Core](https://github.com/datahub-project/datahub)
- [DataHub Skills repository](https://github.com/datahub-project/datahub-skills)
- [Hackathon Slack](https://join.slack.com/t/datahubspace/shared_invite/zt-3rxzw3uww-7F2k5mDpjKXIGLskiQPwLQ)
- [DataHub Town Halls](https://datahub.com/community/datahub-town-halls/)

These are integration surfaces and references, not claims that Predicate has
reimplemented or shipped each DataHub product. The review page labels the
current live path separately from prototype and documentation paths.

## Judge criteria map

| Criterion | Concrete proof in Predicate |
| --- | --- |
| Use of DataHub | Live GraphQL evidence extraction, real URN discovery, and DataHub-backed decisions |
| Technical execution | CLI, SDK, review API, browser panel prototype, tests, and Docker quickstart path |
| Originality | Capability-specific AI admission decisions with explainable failed terms |
| Real-world usefulness | Freshness, assertions, lineage, ownership, usage, and incident checks |
| Submission quality | One local runbook, honest public fixture labeling, and a reproducible demo path |
