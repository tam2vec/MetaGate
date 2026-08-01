# Trust Timeline

Trust is event-valid, not a one-time audit result.

```text
10:00  Predicate Certificate issued
       Generate executive metrics: certified

10:15  Freshness SLA violated in DataHub
       Metadata event received

10:16  Affected graph rescanned
       Generate executive metrics: blocked

10:45  Freshness assertion repaired
       Metadata event received

10:46  Readiness Diff generated
       Generate executive metrics: certified again
```

The history store preserves each certificate and the scanner compares the new
result with the previous one. A relevant DataHub metadata change invalidates
the previous trust decision.
