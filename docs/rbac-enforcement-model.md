# RBAC Enforcement Model

Predicate does not replace DataHub auth. It uses DataHub policy controls as the
authority boundary.

## Production Roles

| Role | Permission |
| --- | --- |
| Requester | Can request an AI readiness verdict for assets they can access. |
| AI agent | Inherits the requester's DataHub permissions. |
| Metadata owner | Repairs missing ownership, glossary, lineage, assertion, and freshness evidence. |
| Steward | Can approve or reject overrides. |
| Auditor | Reviews decision records and override reasons. |

## Enforcement Rules

1. DataHub decides whether a user can request a verdict.
2. Predicate reads only metadata visible to the request context.
3. `PROCEED` allows the requested action within the returned constraints.
4. `CAUTION` allows only constrained or read-only behavior.
5. `BLOCKED` prevents the requested action.
6. Only a designated steward can override `BLOCKED`.
7. Every override requires a human reason.
8. Every override is appended to the decision record.

## Decision Record

```json
{
  "decision_id": "cg-2026-08-01-0001",
  "requested_by": "urn:li:corpuser:analyst",
  "asset_urn": "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)",
  "capability": "autonomous-agent-action",
  "status": "BLOCKED",
  "override": {
    "allowed": false,
    "required_role": "Data Steward",
    "reason_required": true
  }
}
```

## Demo Wording

Use:

> Predicate defines the enforcement model: DataHub policies decide who can ask,
> the AI agent inherits that user's permissions, and any override of a blocked
> decision requires a steward reason and becomes auditable.

Avoid:

> Predicate ships complete enterprise auth out of the box.
