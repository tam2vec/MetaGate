# DataHub AI Readiness Skill

**Predicate helps teams know when AI is allowed to act.**

This is the packaged prototype shape for a DataHub Skill/plugin.

## Input

```json
{
  "urn": "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)",
  "policy": "enterprise-ai"
}
```

## Output

```json
{
  "readiness_score": 97.5,
  "confidence": 97.25,
  "requested_action": "autonomous-agent-action",
  "decision": "blocked",
  "decision_id": "pred-...",
  "constraint_contract": {
    "allowed_action": null,
    "forbidden_actions": ["autonomous-agent-action"],
    "required_human_approval": true,
    "evidence": {},
    "blocking_reasons": ["..."]
  }
}
```

## Callable contract

Install the repository with `pip install -e .`, then use
`context_gradient.skill:certify` with an entity URN and policy path. The result
contains the allow/block capability decision, evidence, confidence, gaps,
remediation, and context contract.

The live adapter calls DataHub GraphQL. Deployment-specific write-back uses the
configured certificate and task mutation documents, keeping the SDK stable
across DataHub versions. The Skill and Review API use the same latest-assertion,
freshness, lineage, and unavailable-evidence rules.

For a local smoke test after installing the repository:

```bash
predicate-skill \
  "urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)" \
  --policy examples/policies/enterprise_ai.yml \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --capability autonomous-agent-action
```

The default is read-only. Add `--writeback` only after configuring and
authorizing the deployment-specific mutation and read-back query.

For the asset-page UI, see `../datahub-embed/`. The Skill produces the decision
contract; the embed renders the compact DataHub panel and links to the full
Predicate Review.
