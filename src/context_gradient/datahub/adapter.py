from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from typing import Any, Dict, Iterable, Protocol
from urllib.request import Request, urlopen

from context_gradient.sdk.models import EntityNode, EvidenceBundle, EvidenceItem, EvidenceKind
from context_gradient.sdk.cache import JsonCache


class DataHubClient(Protocol):
    def get_entity(self, urn: str) -> Dict[str, Any]:
        ...

    def get_neighbors(self, urn: str) -> Iterable[Dict[str, Any]]:
        ...

    def write_certificate(self, urn: str, certificate: Dict[str, Any]) -> None:
        ...

    def create_remediation_task(self, urn: str, title: str, body: str) -> None:
        ...


class DataHubEvidenceExtractor:
    def __init__(self, client: DataHubClient, cache: JsonCache | None = None, max_hops: int = 3):
        self.client = client
        self.cache = cache
        self.max_hops = max(1, max_hops)

    def bundle(self, urn: str) -> EvidenceBundle:
        if self.cache:
            cached = self.cache.get(urn)
            if cached:
                return self._bundle_from_dict(cached)
        entity = self._node(self.client.get_entity(urn))
        neighbors = {}
        frontier = [urn]
        visited = {urn}
        for _ in range(self.max_hops):
            next_frontier = []
            for current in frontier:
                for raw in self.client.get_neighbors(current):
                    neighbor_urn = raw["urn"]
                    if neighbor_urn in visited:
                        continue
                    visited.add(neighbor_urn)
                    neighbors[neighbor_urn] = self._node(raw)
                    next_frontier.append(neighbor_urn)
            frontier = next_frontier
            if not frontier:
                break
        bundle = EvidenceBundle(entity=entity, neighbors=neighbors)
        if self.cache:
            self.cache.set(urn, self._bundle_to_dict(bundle))
        return bundle

    def invalidate(self, urn: str) -> None:
        if self.cache:
            self.cache.delete(urn)

    def _node(self, raw: Dict[str, Any]) -> EntityNode:
        raw_evidence = [self._evidence(kind, raw.get(kind.value)) for kind in EvidenceKind]
        raw_evidence = self._detect_contradictions(raw, raw_evidence)
        return EntityNode(
            urn=raw["urn"],
            type=raw.get("type", "dataset"),
            properties=raw.get("properties", {}),
            evidence=raw_evidence,
            upstreams=raw.get("upstreams", []),
            downstreams=raw.get("downstreams", []),
        )

    def _detect_contradictions(self, raw: Dict[str, Any], evidence: list[EvidenceItem]) -> list[EvidenceItem]:
        explicit = raw.get("contradictions", {})
        description = str((raw.get("description") or {}).get("text", "")).lower()
        terms = " ".join(str(term).lower() for term in (raw.get("glossary") or {}).get("terms", []))
        lexical_conflict = any(
            left in description and right in terms
            for left, right in (("gross", "net"), ("net", "gross"), ("daily", "monthly"), ("monthly", "daily"))
        )
        return [
            EvidenceItem(
                kind=item.kind, present=item.present, complete=item.complete, stale=item.stale,
                contradictory=item.contradictory or bool(explicit.get(item.kind.value, False)) or (item.kind == EvidenceKind.GLOSSARY and lexical_conflict),
                confidence=item.confidence, weight=item.weight, observed_at=item.observed_at, details=item.details,
            )
            for item in evidence
        ]

    def _evidence(self, kind: EvidenceKind, value: Any) -> EvidenceItem:
        details = value if isinstance(value, dict) else {"value": value}
        observed_at = details.get("observed_at")
        if isinstance(observed_at, str):
            observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        else:
            observed = datetime.now(timezone.utc)
        explicit_present = details.get("present")
        present = (
            bool(explicit_present)
            if explicit_present is not None
            else value is not None and not details.get("missing", False)
        )
        return EvidenceItem(
            kind=kind,
            present=present,
            complete=not details.get("incomplete", False),
            stale=details.get("stale", False),
            contradictory=details.get("contradictory", False),
            confidence=float(details.get("confidence", 0.8 if present else 0.0)),
            observed_at=observed,
            details=details,
        )

    def _bundle_to_dict(self, bundle: EvidenceBundle) -> Dict[str, Any]:
        def node(value: EntityNode) -> Dict[str, Any]:
            return {
                "urn": value.urn, "type": value.type, "properties": value.properties,
                "upstreams": value.upstreams, "downstreams": value.downstreams,
                "evidence": [{
                    "kind": item.kind.value, "present": item.present, "complete": item.complete,
                    "stale": item.stale, "contradictory": item.contradictory,
                    "confidence": item.confidence, "weight": item.weight,
                    "observed_at": item.observed_at.isoformat(), "details": item.details,
                } for item in value.evidence],
            }
        return {"entity": node(bundle.entity), "neighbors": {urn: node(value) for urn, value in bundle.neighbors.items()}}

    def _bundle_from_dict(self, value: Dict[str, Any]) -> EvidenceBundle:
        def node(raw: Dict[str, Any]) -> EntityNode:
            evidence = []
            for item in raw.get("evidence", []):
                evidence.append(EvidenceItem(
                    kind=EvidenceKind(item["kind"]), present=item["present"], complete=item.get("complete", True),
                    stale=item.get("stale", False), contradictory=item.get("contradictory", False),
                    confidence=item.get("confidence", 1.0), weight=item.get("weight", 1.0),
                    observed_at=datetime.fromisoformat(item["observed_at"]), details=item.get("details", {}),
                ))
            return EntityNode(urn=raw["urn"], type=raw.get("type", "dataset"), properties=raw.get("properties", {}), evidence=evidence, upstreams=raw.get("upstreams", []), downstreams=raw.get("downstreams", []))
        return EvidenceBundle(entity=node(value["entity"]), neighbors={urn: node(raw) for urn, raw in value.get("neighbors", {}).items()})


class DataHubWriteback:
    def __init__(self, client: DataHubClient):
        self.client = client

    def publish(self, urn: str, certificate: Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(self.client, GraphQLDataHubClient) and not os.environ.get("DATAHUB_CERTIFICATE_MUTATION"):
            raise RuntimeError(
                "Live write-back is not configured. Set DATAHUB_CERTIFICATE_MUTATION "
                "after testing an approved mutation in a non-production namespace."
            )
        self.client.write_certificate(urn, certificate)
        tasks_created = 0
        for gap in certificate.get("gaps", []):
            self.client.create_remediation_task(
                urn,
                f"AI readiness: {gap['evidence_kind']} is {gap['type']}",
                gap["recommendation"],
            )
            tasks_created += 1
        receipt = {"urn": urn, "certificate_written": True, "tasks_requested": tasks_created}
        reader = getattr(self.client, "get_written_certificate", None)
        if reader and reader(urn) is None:
            raise RuntimeError(f"DataHub write-back could not be verified for {urn}")
        return receipt


class GraphQLDataHubClient:
    """Configurable stdlib client for a DataHub GraphQL deployment."""

    QUERY = """
    query ContextGradientEntity($urn: String!) {
      entity(urn: $urn) {
        urn type
        editableProperties { description }
        ownership { owners { owner { urn } } }
        glossaryTerms { terms { term { urn } } }
        domain { domain { urn } }
        tags { tags { tag { urn } } }
        upstreamLineage { upstreams { entity { urn } } }
        downstreamLineage { downstreams { entity { urn } } }
        fineGrainedLineages { fineGrainedLineages { upstreams downstreams } }
        assertions { assertions { urn } }
        incidents { incidents { urn } }
        usageStats { buckets { duration { count } } }
        dashboards { relationships { entity { urn } } }
        charts { relationships { entity { urn } } }
        mlModels { relationships { entity { urn } } }
        properties { key value }
      }
    }
    """

    DATASET_FRAGMENT_QUERY = """
    query ContextGradientEntity($urn: String!) {
      entity(urn: $urn) {
        urn
        type
        ... on Dataset {
          editableProperties { description }
          ownership { owners { owner { ... on CorpUser { urn } } } }
          glossaryTerms { terms { term { urn } } }
          domain { domain { urn } }
          tags { tags { tag { urn } } }
          assertions { assertions { urn } }
          incidents { incidents { urn } }
        }
      }
    }
    """

    def __init__(self, endpoint: str | None = None, token: str | None = None, timeout: int = 30, query: str | None = None):
        self.endpoint = endpoint or os.environ.get("DATAHUB_GRAPHQL_URL", "http://localhost:8080/api/graphql")
        self.token = token or os.environ.get("DATAHUB_TOKEN")
        self.timeout = timeout
        self.query = query or os.environ.get("DATAHUB_ENTITY_QUERY", self.QUERY)

    def get_entity(self, urn: str) -> Dict[str, Any]:
        try:
            raw = self._request(self.query, {"urn": urn}).get("entity")
        except RuntimeError as error:
            if self.query == self.QUERY and "FieldUndefined" in str(error):
                raw = self._request(self.DATASET_FRAGMENT_QUERY, {"urn": urn}).get("entity")
            else:
                raise
        if not raw:
            raise KeyError(f"DataHub entity not found: {urn}")
        return self._normalize(raw, urn)

    def get_neighbors(self, urn: str) -> Iterable[Dict[str, Any]]:
        entity = self.get_entity(urn)
        neighbors = set(entity.get("upstreams", []) + entity.get("downstreams", []))
        return [self.get_entity(neighbor) for neighbor in neighbors]

    def write_certificate(self, urn: str, certificate: Dict[str, Any]) -> None:
        mutation = os.environ.get("DATAHUB_CERTIFICATE_MUTATION")
        if mutation:
            self._request(mutation, {"urn": urn, "certificate": json.dumps(certificate)})

    def create_remediation_task(self, urn: str, title: str, body: str) -> None:
        mutation = os.environ.get("DATAHUB_TASK_MUTATION")
        if mutation:
            self._request(mutation, {"urn": urn, "title": title, "body": body})

    def _request(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(self.endpoint, data=json.dumps({"query": query, "variables": variables}).encode(), headers=headers, method="POST")
        with urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode())
        if payload.get("errors"):
            raise RuntimeError(json.dumps(payload["errors"]))
        return payload.get("data", {})

    def _normalize(self, raw: Dict[str, Any], urn: str) -> Dict[str, Any]:
        raw_properties = {item["key"]: item.get("value") for item in raw.get("properties", []) if item.get("key")}
        ownership = raw.get("ownership") or {}
        owners = [item.get("owner", {}).get("urn") for item in ownership.get("owners", [])]
        terms = [item.get("term", {}).get("urn") for item in (raw.get("glossaryTerms") or {}).get("terms", [])]
        domains = (raw.get("domain") or {}).get("domain", {}).get("urn")
        tags = [item.get("tag", {}).get("urn") for item in (raw.get("tags") or {}).get("tags", [])]
        upstreams = [item.get("entity", {}).get("urn") for item in (raw.get("upstreamLineage") or {}).get("upstreams", [])]
        downstreams = [item.get("entity", {}).get("urn") for item in (raw.get("downstreamLineage") or {}).get("downstreams", [])]
        dashboards = (raw.get("dashboards") or {}).get("relationships", [])
        charts = (raw.get("charts") or {}).get("relationships", [])
        models = (raw.get("mlModels") or {}).get("relationships", [])
        return {
            "urn": raw.get("urn", urn), "type": raw.get("type", "dataset"),
            "description": {"text": (raw.get("editableProperties") or {}).get("description", "")},
            "ownership": {"owners": [item for item in owners if item]},
            "glossary": {"terms": [item for item in terms if item]},
            "domain": {"urn": domains} if domains else {},
            "tags": {"values": [item for item in tags if item]},
            "lineage": {"upstreams": [item for item in upstreams if item]},
            "column_lineage": {"mappings": raw.get("fineGrainedLineages", {}).get("fineGrainedLineages", [])},
            "assertions": {
                "count": len((raw.get("assertions") or {}).get("assertions", [])),
                "present": bool((raw.get("assertions") or {}).get("assertions", [])),
            },
            "incidents": {"open": len((raw.get("incidents") or {}).get("incidents", [])), "present": True},
            "usage": raw.get("usageStats") or {},
            "freshness": raw.get("freshness") or raw_properties.get("context_gradient.freshness") or {},
            "policy": raw.get("policy") or raw_properties.get("context_gradient.policy") or {},
            "dashboards": {"urns": [item.get("entity", {}).get("urn") for item in dashboards]},
            "charts": {"urns": [item.get("entity", {}).get("urn") for item in charts]},
            "ml_models": {"urns": [item.get("entity", {}).get("urn") for item in models]},
            "downstream_consumers": {"count": len(dashboards) + len(charts) + len(models)},
            "properties": raw_properties,
            "upstreams": [item for item in upstreams if item],
            "downstreams": [item for item in downstreams if item],
        }
