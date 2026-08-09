# MetaGate DataHub Embed Prototype

This folder shows the intended product integration: DataHub remains the asset
page, and MetaGate appears as an AI action panel beside the metadata.

The MVP can run three ways:

1. Read-only CLI or SDK evaluation.
2. Static review console for judges and demos.
3. DataHub embed prototype using the same JSON decision contract.

The embed is intentionally small and framework-neutral so it can be adapted to a
DataHub frontend extension, browser extension, reverse-proxy injection, or a
custom internal DataHub fork.

## User experience

On a DataHub asset page, users should see only the compact decision first:

```text
MetaGate
AI action: autonomous-agent-action
Decision: BLOCKED
Reason: Missing required evidence: assertions
Readiness: 91.22
Confidence: 86.25
Open Full Review
```

The full review opens only when the user wants evidence, failed metagate terms,
policy thresholds, JSON, or remediation guidance.

## Contract

The panel consumes the same output emitted by the CLI:

```json
{
  "allowed": false,
  "capability": "autonomous-agent-action",
  "entity_urn": "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)",
  "reason": "Missing required evidence: assertions; Readiness score below 92.0; Confidence below 88.0",
  "readiness_score": 91.22,
  "confidence": 86.25,
  "action_metagate": {
    "action": "autonomous-agent-action",
    "metagate": "ownership.present && glossary.present && lineage.present && assertions.present && incidents.open == 0 && freshness.present && usage.present && policy.present",
    "result": false,
    "failed_terms": [
      "assertions.present",
      "readiness_score >= 92.0",
      "confidence >= 88.0"
    ],
    "decision": "blocked"
  }
}
```

## Files

- `metagate-panel.js`: dependency-free browser panel renderer.
- `panel-contract.json`: example response contract.
- `metagate-datahub-extension.json`: packaged prototype manifest describing
  mount location, API endpoints, permissions, and safe defaults.

## Production path

For a production DataHub deployment, the panel should call a small MetaGate API:

```text
GET /metagate/evaluate?urn=<asset-urn>&capability=autonomous-agent-action
```

That API can call the SDK, read DataHub GraphQL, and return the JSON contract
above. Write-back should stay disabled until a deployment-specific mutation is
configured and tested.

## Prototype mount sketch

```html
<script src="./metagate-panel.js"></script>
<script>
  fetch("/api/evaluate?urn=" + encodeURIComponent(window.__DATAHUB_URN__) + "&capability=autonomous-agent-action")
    .then((response) => response.json())
    .then((decision) => {
      document
        .querySelector("[data-testid='entity-profile-sidebar']")
        .appendChild(window.MetaGatePanel.create(decision));
    });
</script>
```

For the hackathon MVP, `scripts/serve_review.py` provides that API locally.
