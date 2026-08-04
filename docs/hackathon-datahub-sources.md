# Hackathon DataHub Sources

Predicate can evaluate any dataset that exists in the connected DataHub. The
hackathon materials include these useful sources:

| Source | Best use | How Predicate uses it |
| --- | --- | --- |
| `showcase-ecommerce` | Rich cross-platform graph with lineage, governance, glossary, and domains | Evaluate loaded dataset URNs from the pack |
| `bootstrap` | Small starter graph for a quick smoke test | Evaluate loaded dataset URNs from the pack |
| `nyc-taxi` | Freshness and pipeline stress case | Evaluate the dataset URNs created by its recipe |
| `healthcare` | Synthetic quality and sensitive-data scenario | Evaluate the dataset URNs created by its recipe |
| `fiction-retail` | Clean multi-table analytics scenario | Evaluate the dataset URNs created by its recipe |

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

Predicate's six-item dashboard is the stable demo set. A newly loaded
hackathon asset is checked with the **Check another DataHub asset** field:

```text
urn:li:dataset:(urn:li:dataPlatform:<platform>,<name>,PROD)
```

After entering the URN, select **Check asset**. Predicate then reads the
current DataHub metadata and adds that result to the review page. It does not
invent a score for a pack that has not been loaded or for an asset whose URN
has not been provided.

To make a pack part of the fixed six-item demo, replace one of the six demo
URNs in `scripts/start_predicate_review.sh` and reinstall the autostart
service. Keeping the dashboard fixed prevents the asset count from changing
when a DataHub pack is loaded or unavailable.
