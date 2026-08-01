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
  "certified_capabilities": [],
  "blocked_capabilities": [],
  "gaps": [],
  "recommendations": [],
  "context_contract": {}
}
```

## Callable contract

Install the repository with `pip install -e .`, then use
`context_gradient.skill:certify` with an entity URN and policy path. The result
contains the allow/block capability decision, evidence, confidence, gaps,
remediation, and context contract.

The live adapter calls DataHub GraphQL. Deployment-specific write-back uses the
configured certificate and task mutation documents, keeping the SDK stable
across DataHub versions.

For the asset-page UI, see `../datahub-embed/`. The Skill produces the decision
contract; the embed renders the compact DataHub panel and links to the full
Predicate Review.
