from __future__ import annotations

from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import json
import os
import time
from typing import Any, Dict, Iterable, Protocol
from urllib.request import Request, urlopen

from context_gradient.sdk.models import EntityNode, EvidenceBundle, EvidenceItem, EvidenceKind
from context_gradient.sdk.cache import JsonCache


# CLI, Review, and the browser-facing API must assess the same graph. A single
# hop is enough to show direct blast radius without turning every refresh into
# a recursive crawl of the whole catalog.
DEFAULT_MAX_HOPS = 1


class DataHubClient(Protocol):
    def get_entity(self, urn: str) -> Dict[str, Any]:
        ...

    def get_neighbors(self, urn: str) -> Iterable[Dict[str, Any]]:
        ...

    def write_certificate(self, urn: str, certificate: Dict[str, Any]) -> None:
        ...

    def create_remediation_task(self, urn: str, title: str, body: str) -> None:
        ...


PREDICATE_CONTRACT_PROPERTY = "predicate.ai_context_contract"


class DataHubEvidenceExtractor:
    def __init__(self, client: DataHubClient, cache: JsonCache | None = None, max_hops: int = DEFAULT_MAX_HOPS):
        self.client = client
        self.cache = cache
        self.max_hops = max(1, max_hops)

    def bundle(self, urn: str) -> EvidenceBundle:
        if self.cache:
            cached = self.cache.get(urn)
            if cached:
                return self._bundle_from_dict(cached)
        consistent_reader = getattr(self.client, "get_entity_consistent", None)
        entity = self._node(consistent_reader(urn) if consistent_reader else self.client.get_entity(urn))
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
        available_kinds = set(raw.get("_available_evidence", []))
        unavailable_reasons = raw.get("_unavailable_evidence", {})
        availability_declared = "_available_evidence" in raw
        raw_evidence = []
        for kind in EvidenceKind:
            value = raw.get(kind.value)
            if availability_declared and kind.value not in available_kinds:
                value = {
                    "unavailable": True,
                    "availability_reason": unavailable_reasons.get(
                        kind.value,
                        "field was not returned by the DataHub response",
                    ),
                }
            raw_evidence.append(self._evidence(kind, value))
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
                available=item.available,
            )
            for item in evidence
        ]

    def _evidence(self, kind: EvidenceKind, value: Any) -> EvidenceItem:
        details = dict(value) if isinstance(value, dict) else {"value": value}
        observed_at = details.get("observed_at")
        if isinstance(observed_at, str):
            observed_time = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        else:
            observed_time = datetime.now(timezone.utc)
            details["_observed_at_inferred"] = True
        explicit_present = details.get("present")
        def has_content(candidate: Any) -> bool:
            if candidate is None:
                return False
            if isinstance(candidate, dict):
                evidence_fields = {
                    key: item
                    for key, item in candidate.items()
                    if key not in {
                        "confidence", "observed_at", "incomplete", "stale",
                        "contradictory", "present", "missing", "source",
                        "timestamp_source",
                    }
                }
                return bool(evidence_fields) and any(has_content(item) for item in evidence_fields.values())
            if isinstance(candidate, (list, tuple, set)):
                return bool(candidate)
            if isinstance(candidate, str):
                return bool(candidate.strip())
            return True

        empty_means_missing = kind in {
            EvidenceKind.DESCRIPTION,
            EvidenceKind.OWNERSHIP,
            EvidenceKind.GLOSSARY,
            EvidenceKind.DOMAIN,
            EvidenceKind.TAGS,
            EvidenceKind.LINEAGE,
            EvidenceKind.COLUMN_LINEAGE,
            EvidenceKind.ASSERTIONS,
            EvidenceKind.FRESHNESS,
            EvidenceKind.USAGE,
            EvidenceKind.POLICY,
        }
        has_observed_content = has_content(value) if empty_means_missing else value is not None
        present = (
            bool(explicit_present)
            if explicit_present is not None
            else has_observed_content and not details.get("missing", False)
        )
        available = not details.get("unavailable", False)
        if not available:
            present = False
        if present and "confidence" not in details:
            details["quality_factor"] = self._infer_quality(kind, details)
        return EvidenceItem(
            kind=kind,
            present=present,
            complete=not details.get("incomplete", False),
            stale=details.get("stale", False),
            contradictory=details.get("contradictory", False),
            confidence=float(details.get("confidence", details.get("quality_factor", 0.0) if present else 0.0)),
            observed_at=observed_time,
            details=details,
            available=available,
        )

    @staticmethod
    def _infer_quality(kind: EvidenceKind, details: Dict[str, Any]) -> float:
        """Estimate evidence richness when a live DataHub response has no confidence field."""
        def bounded(value: float) -> float:
            return round(max(0.45, min(1.0, value)), 4)

        if kind == EvidenceKind.DESCRIPTION:
            text = str(details.get("text", "")).strip()
            return bounded(0.55 + min(len(text) / 240.0, 0.45))
        if kind == EvidenceKind.OWNERSHIP:
            return bounded(0.7 + min(len(details.get("owners", [])) * 0.12, 0.3))
        if kind == EvidenceKind.GLOSSARY:
            return bounded(0.55 + min(len(details.get("terms", [])) * 0.1, 0.45))
        if kind == EvidenceKind.LINEAGE:
            links = len(details.get("upstreams", [])) + len(details.get("downstreams", []))
            return bounded(0.55 + min(links * 0.09, 0.45))
        if kind == EvidenceKind.COLUMN_LINEAGE:
            return bounded(0.55 + min(float(details.get("mapped_columns", 0)) * 0.06, 0.45))
        if kind == EvidenceKind.ASSERTIONS:
            total = int(details.get("passing", 0) or 0) + int(details.get("failing", 0) or 0)
            return bounded(0.55 + min(total * 0.06, 0.25) + (0.2 if total and not details.get("failing") else 0.0))
        if kind == EvidenceKind.USAGE:
            return bounded(0.6 + min(float(details.get("weekly_users", 0) or 0) / 500.0, 0.4))
        if kind == EvidenceKind.POLICY:
            return bounded(0.85 if details.get("profile") else 0.55)
        if kind == EvidenceKind.FRESHNESS:
            return bounded(0.9 if details.get("timestamp") or details.get("observed_at") else 0.6)
        return 0.75

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
                    "available": item.available,
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
                    available=item.get("available", True),
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
        if isinstance(self.client, GraphQLDataHubClient) and not os.environ.get("DATAHUB_CERTIFICATE_QUERY"):
            raise RuntimeError(
                "Live write-back verification is not configured. Set DATAHUB_CERTIFICATE_QUERY "
                "before enabling the mutation. Predicate will not write without read-back verification."
            )
        try:
            self.client.write_certificate(urn, certificate)
        except Exception as error:
            raise RuntimeError(f"DataHub write-back failed for {urn}: {error}") from error
        receipt = {
            "urn": urn,
            "certificate_written": True,
            "written_at": datetime.now(timezone.utc).isoformat(),
        }
        transport = getattr(self.client, "transport", None)
        if transport:
            receipt["transport"] = transport
        property_name = getattr(self.client, "property_name", None)
        if property_name:
            receipt["property_name"] = property_name
        reader = getattr(self.client, "get_written_certificate", None)
        if not reader:
            raise RuntimeError("Write-back verification is not configured. Set DATAHUB_CERTIFICATE_QUERY.")
        try:
            attempts = max(1, int(os.environ.get("PREDICATE_WRITEBACK_READBACK_ATTEMPTS", "4")))
            interval = max(0.0, float(os.environ.get("PREDICATE_WRITEBACK_READBACK_INTERVAL", "0.5")))
            readback = None
            for attempt in range(attempts):
                readback = reader(urn)
                if readback is not None or attempt == attempts - 1:
                    break
                time.sleep(interval)
        except Exception as error:
            raise RuntimeError(f"DataHub write-back was sent but read-back failed for {urn}: {error}") from error
        if readback is None:
            raise RuntimeError(f"DataHub write-back could not be verified for {urn}")
        if isinstance(readback, dict):
            returned_urn = readback.get("urn") or readback.get("entity_urn") or readback.get("datasetUrn")
            if returned_urn and returned_urn != urn:
                raise RuntimeError(f"DataHub read-back returned {returned_urn}, expected {urn}")
            expected_decision = certificate.get("decision")
            returned_decision = readback.get("decision") or readback.get("status")
            if expected_decision and returned_decision and str(returned_decision).lower() != str(expected_decision).lower():
                raise RuntimeError(
                    f"DataHub read-back decision {returned_decision!r} does not match {expected_decision!r} for {urn}"
                )
            expected_decision_id = certificate.get("decision_id")
            returned_decision_id = readback.get("decision_id")
            if expected_decision_id and returned_decision_id and returned_decision_id != expected_decision_id:
                raise RuntimeError(
                    f"DataHub read-back decision_id {returned_decision_id!r} does not match "
                    f"{expected_decision_id!r} for {urn}"
                )
            stored_certificate = readback.get("_predicate_certificate")
            if stored_certificate is not None and stored_certificate != certificate:
                raise RuntimeError(f"DataHub read-back contract does not match the written contract for {urn}")
            receipt["readback_fields"] = sorted(readback.keys())
        receipt["read_back_at"] = datetime.now(timezone.utc).isoformat()
        receipt["verified_readback"] = True
        tasks_created = 0
        for gap in certificate.get("gaps", []):
            self.client.create_remediation_task(
                urn,
                f"AI readiness: {gap['evidence_kind']} is {gap['type']}",
                gap["recommendation"],
            )
            tasks_created += 1
        receipt["tasks_requested"] = tasks_created
        return receipt


class DataHubRestWritebackClient:
    """Write and read one Predicate contract through DataHub's REST client.

    This deliberately uses the DatasetProperties aspect rather than guessing a
    GraphQL mutation. Existing dataset properties are preserved and only the
    Predicate custom property is upserted. The DataHub Python SDK is imported
    lazily so fixture-only installs do not need the SDK at import time.
    """

    transport = "datahub-rest-sdk"
    property_name = PREDICATE_CONTRACT_PROPERTY

    def __init__(self, gms_url: str, token: str | None = None, graph: Any | None = None):
        self.gms_url = gms_url.rstrip("/")
        self.token = token
        self._graph = graph

    def _get_graph(self) -> Any:
        if self._graph is None:
            try:
                from datahub.ingestion.graph.client import DataHubGraph
                from datahub.ingestion.graph.config import DatahubClientConfig
            except ImportError as error:
                raise RuntimeError(
                    "The DataHub Python SDK is required for REST write-back. "
                    "Install it with: python3 -m pip install 'acryl-datahub[all]'."
                ) from error
            self._graph = DataHubGraph(
                DatahubClientConfig(server=self.gms_url, token=self.token, timeout_sec=30)
            )
        return self._graph

    @staticmethod
    def _properties_aspect(graph: Any, urn: str) -> Any:
        from datahub.metadata.schema_classes import DatasetPropertiesClass

        return graph.get_aspect(urn, DatasetPropertiesClass)

    def write_certificate(self, urn: str, certificate: Dict[str, Any]) -> None:
        from datahub.emitter.mcp import MetadataChangeProposalWrapper
        from datahub.metadata.schema_classes import DatasetPropertiesClass

        graph = self._get_graph()
        existing = self._properties_aspect(graph, urn)
        custom_properties = dict(getattr(existing, "customProperties", {}) or {})
        custom_properties[PREDICATE_CONTRACT_PROPERTY] = json.dumps(
            certificate, sort_keys=True, separators=(",", ":")
        )
        if existing is None:
            aspect = DatasetPropertiesClass(customProperties=custom_properties)
        else:
            existing.customProperties = custom_properties
            aspect = existing
        graph.emit(MetadataChangeProposalWrapper(entityUrn=urn, aspect=aspect))

    def get_written_certificate(self, urn: str) -> Dict[str, Any] | None:
        graph = self._get_graph()
        aspect = self._properties_aspect(graph, urn)
        if aspect is None:
            return None
        raw = (getattr(aspect, "customProperties", {}) or {}).get(PREDICATE_CONTRACT_PROPERTY)
        if not raw:
            return None
        try:
            certificate = json.loads(raw)
        except (TypeError, ValueError) as error:
            raise RuntimeError(
                f"DataHub property {PREDICATE_CONTRACT_PROPERTY} is not valid JSON for {urn}"
            ) from error
        if not isinstance(certificate, dict):
            raise RuntimeError(
                f"DataHub property {PREDICATE_CONTRACT_PROPERTY} is not a JSON object for {urn}"
            )
        return {"urn": urn, "_predicate_certificate": certificate, **certificate}

    def get_entity(self, urn: str) -> Dict[str, Any]:
        raise NotImplementedError("REST write-back client is only for contract publication")

    def get_neighbors(self, urn: str) -> Iterable[Dict[str, Any]]:
        return []

    def create_remediation_task(self, urn: str, title: str, body: str) -> None:
        # Remediation tasks are local Predicate records unless a deployment
        # separately configures a task mutation. Do not invent a REST aspect.
        return None


class GraphQLDataHubClient:
    """Configurable stdlib client for a DataHub GraphQL deployment."""

    CORE_QUERY = """
    query ContextGradientCore($urn: String!) {
      dataset(urn: $urn) {
        urn
        properties { description }
        ownership {
          owners {
            owner {
              ... on CorpUser { urn }
              ... on CorpGroup { urn }
            }
          }
        }
        glossaryTerms { terms { term { urn } } }
        domain { domain { urn } }
        tags { tags { tag { urn } } }
      }
    }
    """

    OPTIONAL_QUERIES = {
        "ownership": """
        query ContextGradientOwnership($urn: String!) {
          dataset(urn: $urn) {
            ownership {
              owners {
                owner {
                  ... on CorpUser { urn username }
                  ... on CorpGroup { urn name }
                }
              }
            }
          }
        }
        """,
        "glossary": """
        query ContextGradientGlossary($urn: String!) {
          dataset(urn: $urn) { glossaryTerms { terms { term { urn name } } } }
        }
        """,
        "domain": """
        query ContextGradientDomain($urn: String!) {
          dataset(urn: $urn) { domain { domain { urn name } } }
        }
        """,
        "tags": """
        query ContextGradientTags($urn: String!) {
          dataset(urn: $urn) { tags { tags { tag { urn name } } } }
        }
        """,
        "assertions": """
        query ContextGradientAssertions($urn: String!) {
          dataset(urn: $urn) {
            assertions(start: 0, count: 100) {
              assertions {
                urn
                info { type description }
                runEvents(limit: 100) {
                  total
                  runEvents {
                    timestampMillis
                    status
                    result { type actualAggValue externalUrl }
                  }
                }
              }
            }
          }
        }
        """,
        "incidents": """
        query ContextGradientIncidents($urn: String!) {
          dataset(urn: $urn) {
            incidents(state: ACTIVE, start: 0, count: 100) {
              total
              incidents { urn title description status { state } }
            }
          }
        }
        """,
        "column_lineage": """
        query ContextGradientColumnLineage($urn: String!) {
          dataset(urn: $urn) {
            fineGrainedLineages { fineGrainedLineages { upstreams downstreams } }
          }
        }
        """,
        "schema": """
        query ContextGradientSchema($urn: String!) {
          dataset(urn: $urn) {
            schemaMetadata {
              fields { fieldPath }
            }
          }
        }
        """,
        "usage": """
        query ContextGradientUsage($urn: String!) {
          dataset(urn: $urn) { usageStats { buckets { duration { count } } } }
        }
        """,
        "dashboards": """
        query ContextGradientDashboards($urn: String!) {
          dataset(urn: $urn) { dashboards { relationships { entity { urn } } } }
        }
        """,
        "charts": """
        query ContextGradientCharts($urn: String!) {
          dataset(urn: $urn) { charts { relationships { entity { urn } } } }
        }
        """,
        "ml_models": """
        query ContextGradientModels($urn: String!) {
          dataset(urn: $urn) { mlModels { relationships { entity { urn } } } }
        }
        """,
    }

    QUERY = """
    query ContextGradientEntity($urn: String!) {
      dataset(urn: $urn) {
        urn
        properties { description }
        ownership {
          owners {
            owner {
              ... on CorpUser { urn }
              ... on CorpGroup { urn }
            }
          }
        }
        glossaryTerms { terms { term { urn } } }
        domain { domain { urn } }
        tags { tags { tag { urn } } }
        fineGrainedLineages { fineGrainedLineages { upstreams downstreams } }
        usageStats { buckets { duration { count } } }
        dashboards { relationships { entity { urn } } }
        charts { relationships { entity { urn } } }
        mlModels { relationships { entity { urn } } }
        assertions(start: 0, count: 100) {
          assertions {
            urn
            info { type description }
            runEvents(limit: 100) {
              total
              runEvents {
                timestampMillis
                status
                result { type actualAggValue externalUrl }
              }
            }
          }
        }
        incidents(state: ACTIVE, start: 0, count: 100) {
          total
          incidents { urn title description status { state } }
        }
      }
    }
    """

    # Older DataHub deployments may not expose assertion run history in the
    # Dataset connection. This fallback still reads the asset, but marks the
    # quality result as unavailable rather than treating an URN as a pass.
    BASE_QUERY = """
    query ContextGradientEntity($urn: String!) {
      dataset(urn: $urn) {
        urn
        properties { description }
      }
    }
    """

    SEARCH_DATASETS_QUERY = """
    query PredicateDatasetDiscovery($query: String!, $start: Int!, $count: Int!) {
      search(input: { type: DATASET, query: $query, start: $start, count: $count }) {
        searchResults { entity { urn type } }
      }
    }
    """

    LINEAGE_QUERY = """
    query ContextGradientLineage($urn: String!) {
      scrollAcrossLineage(
        input: { query: "*", urn: $urn, count: 100, direction: __DIRECTION__ }
      ) {
        searchResults {
          entity { urn type }
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
        degraded_error = None
        unavailable = {}
        if self.query == self.QUERY:
            try:
                core = self._request(self.CORE_QUERY, {"urn": urn})
                raw = core.get("dataset") or core.get("entity")
            except RuntimeError as error:
                if "FieldUndefined" in str(error):
                    degraded_error = str(error)
                    base = self._request(self.BASE_QUERY, {"urn": urn})
                    raw = base.get("dataset") or base.get("entity")
                else:
                    raise
            if raw:
                # Optional aspects are deliberately isolated. A deployment
                # that lacks usage or column lineage must not erase valid
                # assertion or incident evidence from the same asset.
                for kind, query in self.OPTIONAL_QUERIES.items():
                    try:
                        optional_response = self._request(query, {"urn": urn})
                        optional = optional_response.get("dataset") or optional_response.get("entity") or {}
                        if kind == "assertions":
                            raw["assertions"] = optional.get("assertions")
                        elif kind == "incidents":
                            raw["incidents"] = optional.get("incidents")
                        elif kind == "column_lineage":
                            raw["fineGrainedLineages"] = optional.get("fineGrainedLineages")
                        elif kind == "schema":
                            if "schemaMetadata" in optional:
                                raw["schemaMetadata"] = optional.get("schemaMetadata")
                        else:
                            field = kind if kind != "ml_models" else "mlModels"
                            if field in optional:
                                raw[field] = optional.get(field)
                    except RuntimeError as error:
                        unavailable["column_lineage" if kind == "schema" else kind] = str(error)
        else:
            data = self._request(self.query, {"urn": urn})
            raw = data.get("dataset") or data.get("entity")
        if not raw:
            raise KeyError(f"DataHub entity not found: {urn}")
        if self.query == self.QUERY:
            raw = dict(raw)
            if degraded_error:
                raw["_query_degraded"] = degraded_error
            if unavailable:
                raw["_unavailable_evidence"] = unavailable
            # These two reads are independent. Keeping them concurrent cuts
            # the latency of every live entity read without changing evidence.
            with ThreadPoolExecutor(max_workers=2) as pool:
                upstreams = pool.submit(self._lineage_entities, urn, "UPSTREAM")
                downstreams = pool.submit(self._lineage_entities, urn, "DOWNSTREAM")
                try:
                    raw["upstreamLineage"] = {"upstreams": upstreams.result()}
                    raw["downstreamLineage"] = {"downstreams": downstreams.result()}
                except RuntimeError as error:
                    raw["_lineage_unavailable"] = str(error)
                    raw["upstreamLineage"] = {"upstreams": []}
                    raw["downstreamLineage"] = {"downstreams": []}
        return self._normalize(raw, urn)

    def get_entity_consistent(self, urn: str) -> Dict[str, Any]:
        """Retry deployment-lagged reads without turning unknown into absent.

        DataHub writes are asynchronous. A missing optional field on the first
        response is therefore retried, while the final normalized result still
        records the signal as unavailable when the deployment never exposes it.
        """
        attempts = max(1, int(os.environ.get("PREDICATE_CONSISTENCY_ATTEMPTS", "3")))
        interval = max(0.0, float(os.environ.get("PREDICATE_CONSISTENCY_INTERVAL", "0.25")))
        pending_kinds = set(os.environ.get(
            "PREDICATE_CONSISTENCY_SIGNALS",
            "assertions,freshness,usage,column_lineage,incidents",
        ).split(","))
        last = None
        for attempt in range(attempts):
            candidate = self.get_entity(urn)
            unavailable = set((candidate.get("_unavailable_evidence") or {}).keys())
            pending = sorted(item for item in unavailable if item in pending_kinds)
            properties = dict(candidate.get("properties") or {})
            properties["_consistency"] = {
                "attempt": attempt + 1,
                "attempts": attempts,
                "pending_unavailable": pending,
                "source_observed_at": datetime.now(timezone.utc).isoformat(),
            }
            candidate["properties"] = properties
            last = candidate
            if not pending or attempt == attempts - 1:
                return candidate
            time.sleep(interval)
        return last or self.get_entity(urn)

    def list_dataset_urns(self) -> list[str]:
        """Discover all dataset URNs currently present in this DataHub deployment.

        DataHub search responses are paged. Keeping pagination here prevents a
        large datapack from looking complete when only its first page loaded.
        The review server applies its own per-refresh safety cap afterward.
        """
        page_size = 1000
        start = 0
        urns: set[str] = set()
        while True:
            data = self._request(
                self.SEARCH_DATASETS_QUERY,
                {"query": "*", "start": start, "count": page_size},
            )
            results = ((data.get("search") or {}).get("searchResults") or [])
            if not results:
                break
            for item in results:
                entity = item.get("entity") if isinstance(item, dict) else None
                if isinstance(entity, dict) and entity.get("urn"):
                    urns.add(entity["urn"])
            if len(results) < page_size:
                break
            start += len(results)
        return sorted(urns)

    def _lineage_entities(self, urn: str, direction: str) -> list[Dict[str, Any]]:
        """Read lineage through DataHub's supported search API.

        DataHub 1.5 exposes lineage through scrollAcrossLineage rather than
        upstreamLineage/downstreamLineage fields on Dataset.
        """
        try:
            query = self.LINEAGE_QUERY.replace("__DIRECTION__", direction)
            data = self._request(query, {"urn": urn})
        except RuntimeError as error:
            raise RuntimeError(f"DataHub lineage query failed ({direction}): {error}") from error
        results = ((data.get("scrollAcrossLineage") or {}).get("searchResults") or [])
        return [
            {"entity": item.get("entity") or {}}
            for item in results
            if isinstance(item, dict) and item.get("entity", {}).get("urn")
        ]

    def get_neighbors(self, urn: str) -> Iterable[Dict[str, Any]]:
        entity = self.get_entity(urn)
        # _normalize stores lineage under one explicit evidence object. Reading
        # the old top-level keys here silently produced an empty graph and
        # made every score look like an isolated-asset score.
        lineage = entity.get("lineage") or {}
        neighbors = sorted(set(
            (lineage.get("upstreams") or []) + (lineage.get("downstreams") or [])
        ))
        if not neighbors:
            return []
        # Neighbor metadata is independent too. This is especially important
        # for the review page, which evaluates several assets together.
        with ThreadPoolExecutor(max_workers=min(8, len(neighbors))) as pool:
            futures = {pool.submit(self.get_entity, neighbor): neighbor for neighbor in neighbors}
            results = {}
            for future, neighbor in futures.items():
                results[neighbor] = future.result()
        return [results[neighbor] for neighbor in neighbors]

    def write_certificate(self, urn: str, certificate: Dict[str, Any]) -> None:
        mutation = os.environ.get("DATAHUB_CERTIFICATE_MUTATION")
        if mutation:
            self._request(mutation, {"urn": urn, "certificate": json.dumps(certificate)})

    def create_remediation_task(self, urn: str, title: str, body: str) -> None:
        mutation = os.environ.get("DATAHUB_TASK_MUTATION")
        if mutation:
            self._request(mutation, {"urn": urn, "title": title, "body": body})

    def get_written_certificate(self, urn: str) -> Dict[str, Any] | None:
        query = os.environ.get("DATAHUB_CERTIFICATE_QUERY")
        if not query:
            return None
        data = self._request(query, {"urn": urn})
        value = data.get("entity") or data.get("dataset") or data.get("aiContextContract")
        if isinstance(value, dict):
            return value
        return value if value else None

    def _request(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(self.endpoint, data=json.dumps({"query": query, "variables": variables}).encode(), headers=headers, method="POST")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode())
        except Exception as error:
            raise RuntimeError(
                f"DataHub GraphQL request failed at {self.endpoint}: {error}. "
                "Confirm DataHub is running, the URL is correct, and the token has access."
            ) from error
        if payload.get("errors"):
            messages = "; ".join(str(item.get("message", item)) for item in payload["errors"])
            raise RuntimeError(f"DataHub GraphQL rejected the query: {messages}")
        return payload.get("data", {})

    def _normalize(self, raw: Dict[str, Any], urn: str) -> Dict[str, Any]:
        custom_properties = raw.get("customProperties") or []
        raw_properties = {
            item["key"]: item.get("value")
            for item in custom_properties
            if isinstance(item, dict) and item.get("key")
        }
        def identifier(value: Any):
            """Accept the common URN/name shapes returned by DataHub versions."""
            if isinstance(value, str):
                return value or None
            if not isinstance(value, dict):
                return None
            return value.get("urn") or value.get("username") or value.get("name")

        ownership = raw.get("ownership") or {}
        owners = [
            identifier(item.get("owner") if isinstance(item, dict) else item)
            for item in ownership.get("owners", [])
        ]
        terms = [
            identifier(item.get("term") if isinstance(item, dict) else item)
            for item in (raw.get("glossaryTerms") or {}).get("terms", [])
        ]
        domain_value = (raw.get("domain") or {}).get("domain")
        domains = identifier(domain_value)
        tags = [
            identifier(item.get("tag") if isinstance(item, dict) else item)
            for item in (raw.get("tags") or {}).get("tags", [])
        ]
        upstreams = [
            identifier(item.get("entity") if isinstance(item, dict) else item)
            for item in (raw.get("upstreamLineage") or {}).get("upstreams", [])
        ]
        downstreams = [
            identifier(item.get("entity") if isinstance(item, dict) else item)
            for item in (raw.get("downstreamLineage") or {}).get("downstreams", [])
        ]
        dashboards = (raw.get("dashboards") or {}).get("relationships", [])
        charts = (raw.get("charts") or {}).get("relationships", [])
        models = (raw.get("mlModels") or {}).get("relationships", [])
        incident_data = raw.get("incidents")
        incident_items = (incident_data or {}).get("incidents", [])
        fine_grained_lineage = raw.get("fineGrainedLineages") or {}
        schema_metadata = raw.get("schemaMetadata") or {}
        schema_fields = [
            item.get("fieldPath")
            for item in schema_metadata.get("fields", [])
            if isinstance(item, dict) and item.get("fieldPath")
        ]
        assertion_data = raw.get("assertions")
        # DataHub can return the same assertion through multiple relationship
        # edges. Count one assertion once; its runEvents still determine the
        # latest result below.
        assertions_by_key = {}
        for item in (assertion_data or {}).get("assertions", []):
            if not isinstance(item, dict):
                continue
            key = item.get("urn") or f"inline:{len(assertions_by_key)}"
            existing = assertions_by_key.get(key)
            if existing is None:
                assertions_by_key[key] = dict(item)
                continue
            existing_events = (existing.setdefault("runEvents", {})).setdefault("runEvents", [])
            duplicate_events = (item.get("runEvents") or {}).get("runEvents", [])
            existing_events.extend(event for event in duplicate_events if isinstance(event, dict))
        assertion_items = list(assertions_by_key.values())
        latest_results = []
        assertions_without_results = []
        for item in assertion_items:
            if not isinstance(item, dict):
                continue
            events = [
                event for event in ((item.get("runEvents") or {}).get("runEvents") or [])
                if isinstance(event, dict)
            ]
            if events:
                latest = max(events, key=lambda event: int(event.get("timestampMillis") or 0))
                latest_results.append(latest)
            elif any(key in item for key in ("result", "latestResult", "status")):
                latest_results.append(item.get("result") or item.get("latestResult") or {"status": item.get("status")})
            else:
                assertions_without_results.append(item.get("urn", "unknown assertion"))
        latest_statuses = [
            str(event.get("status", "")).upper()
            or str((event.get("result") or {}).get("type", "")).upper()
            for event in latest_results
        ]
        passing_statuses = {"SUCCESS", "COMPLETE", "PASS"}
        failing_statuses = {"FAILURE", "FAIL", "ERROR"}
        latest_passing = sum(status in passing_statuses for status in latest_statuses)
        latest_failing = sum(status in failing_statuses for status in latest_statuses)
        latest_unknown = len(latest_statuses) - latest_passing - latest_failing
        assertion_has_results = bool(assertion_items) and not assertions_without_results and latest_unknown == 0
        freshness_results = []
        for item in assertion_items:
            if not isinstance(item, dict) or str((item.get("info") or {}).get("type", "")).upper() != "FRESHNESS":
                continue
            events = (item.get("runEvents") or {}).get("runEvents") or []
            latest = max(events, key=lambda candidate: int(candidate.get("timestampMillis") or 0), default=None)
            if latest:
                freshness_results.append(latest)
            elif any(key in item for key in ("result", "latestResult", "status")):
                freshness_results.append(item.get("result") or item.get("latestResult") or {"status": item.get("status")})
        mapped_fields = set()
        for mapping in fine_grained_lineage.get("fineGrainedLineages", []) or []:
            if not isinstance(mapping, dict):
                continue
            for side in ("upstreams", "downstreams"):
                values = mapping.get(side) or []
                for value in values:
                    if isinstance(value, str):
                        mapped_fields.add(value)
                    elif isinstance(value, dict) and value.get("fieldPath"):
                        mapped_fields.add(value["fieldPath"])
        missing_columns = sorted(set(schema_fields) - mapped_fields)
        column_lineage_coverage = (
            len(set(schema_fields) & mapped_fields) / len(set(schema_fields))
            if schema_fields else 0.0
        )
        available_evidence = [
            kind for kind, source in (
                ("description", "properties"),
                ("ownership", "ownership"),
                ("glossary", "glossaryTerms"),
                ("domain", "domain"),
                ("tags", "tags"),
            ) if source in raw
        ]
        if "_lineage_unavailable" not in raw and "upstreamLineage" in raw and "downstreamLineage" in raw:
            available_evidence.append("lineage")
        if assertion_data is not None and not raw.get("_query_degraded"):
            available_evidence.append("assertions")
        if "incidents" in raw and not raw.get("_query_degraded"):
            available_evidence.append("incidents")
        if freshness_results and not raw.get("_query_degraded"):
            available_evidence.append("freshness")
        optional_sources = {
            "freshness": "freshness",
            "usageStats": "usage",
            "policy": "policy",
            "dashboards": "dashboards",
            "charts": "charts",
            "mlModels": "ml_models",
        }
        available_evidence.extend(
            normalized for source, normalized in optional_sources.items() if source in raw
        )
        if "fineGrainedLineages" in raw and "schemaMetadata" in raw:
            available_evidence.append("column_lineage")
        unavailable = dict(raw.get("_unavailable_evidence") or {})
        if raw.get("_query_degraded"):
            unavailable["assertions"] = raw["_query_degraded"]
            unavailable["incidents"] = raw["_query_degraded"]
        if raw.get("_lineage_unavailable"):
            unavailable["lineage"] = raw["_lineage_unavailable"]
        # A field omitted from a custom or deployment-specific query is an
        # observation gap, not proof that the asset lacks that metadata.
        expected_sources = {
            "description": "properties",
            "ownership": "ownership",
            "glossary": "glossaryTerms",
            "domain": "domain",
            "tags": "tags",
            "freshness": "freshness",
            "usage": "usageStats",
            "policy": "policy",
        }
        for kind, source in expected_sources.items():
            if source not in raw and kind not in available_evidence:
                unavailable.setdefault(kind, f"{source} was not returned by the DataHub GraphQL response")
        for kind in ("column_lineage", "freshness", "usage"):
            if kind not in available_evidence:
                unavailable.setdefault(kind, "field was not returned by the DataHub GraphQL response")
        observation = {
            "source": "DataHub GraphQL",
            "available_evidence": sorted(set(available_evidence)),
            "unavailable_evidence": unavailable,
            "returned_fields": sorted(raw.keys()),
        }
        usage_stats = raw.get("usageStats") or {}
        usage_buckets = usage_stats.get("buckets") or [] if isinstance(usage_stats, dict) else []
        return {
            "urn": raw.get("urn", urn), "type": raw.get("type", "dataset"),
            "description": {
                "text": (
                    (raw.get("editableProperties") or {}).get("description")
                    or (raw.get("properties") or {}).get("description", "")
                )
            },
            "ownership": {"owners": [item for item in owners if item]},
            "glossary": {"terms": [item for item in terms if item]},
            "domain": {"urn": domains} if domains else {},
            "tags": {"values": [item for item in tags if item]},
            "lineage": {
                "upstreams": [item for item in upstreams if item],
                "downstreams": [item for item in downstreams if item],
            },
            "column_lineage": {
                "mappings": fine_grained_lineage.get("fineGrainedLineages", []),
                "total_columns": len(set(schema_fields)),
                "mapped_columns": len(set(schema_fields) & mapped_fields),
                "missing_columns": missing_columns,
                "coverage": round(column_lineage_coverage, 4),
                "complete": bool(schema_fields) and not missing_columns,
            },
            "assertions": {
                "count": len(assertion_items),
                "present": bool(assertion_items),
                "names": [item.get("urn") for item in assertion_items if isinstance(item, dict)],
                "latest_results": latest_results,
                "passing": latest_passing,
                "failing": latest_failing,
                "unknown": latest_unknown,
                "missing_results": assertions_without_results,
                "latest_all_passing": bool(assertion_items) and latest_passing == len(assertion_items),
                "incomplete": bool(assertion_items) and not assertion_has_results,
                "contradictory": latest_failing > 0,
            },
            # The live query requests ACTIVE incidents. A returned empty list
            # therefore means zero active incidents; a missing/failed field is
            # represented as unavailable instead.
            "incidents": {
                "open": len(incident_items),
                "present": incident_data is not None,
                "items": incident_items,
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "timestamp_source": "DataHub query observation time",
            },
            "usage": dict(usage_stats, **{
                # A query timestamp proves that the query ran, not that usage
                # telemetry was returned. Empty buckets stay missing.
                "present": bool(usage_buckets),
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "timestamp_source": "DataHub query observation time",
            }),
            "freshness": raw.get("freshness") or raw_properties.get("context_gradient.freshness") or (
                {
                    "timestamp": max(
                        (event.get("timestampMillis", 0) for event in freshness_results),
                        default=None,
                    ),
                    "observed_at": datetime.fromtimestamp(
                        max((event.get("timestampMillis", 0) for event in freshness_results), default=0) / 1000,
                        timezone.utc,
                    ).isoformat(),
                    "passed": all(
                        str(event.get("status", "")).upper() in {"SUCCESS", "COMPLETE"}
                        or str((event.get("result") or {}).get("type", "")).upper() in {"SUCCESS", "PASS"}
                        for event in freshness_results
                    ),
                    "stale": not all(
                        str(event.get("status", "")).upper() in {"SUCCESS", "COMPLETE"}
                        or str((event.get("result") or {}).get("type", "")).upper() in {"SUCCESS", "PASS"}
                        for event in freshness_results
                    ),
                    "source": "DataHub assertion runEvents",
                }
                if freshness_results else {}
            ),
            "policy": raw.get("policy") or raw_properties.get("context_gradient.policy") or {},
            "dashboards": {"urns": [item.get("entity", {}).get("urn") for item in dashboards]},
            "charts": {"urns": [item.get("entity", {}).get("urn") for item in charts]},
            "ml_models": {"urns": [item.get("entity", {}).get("urn") for item in models]},
            "downstream_consumers": {"count": len(dashboards) + len(charts) + len(models)},
            "properties": {**raw_properties, "_datahub_observation": observation},
            "upstreams": [item for item in upstreams if item],
            "downstreams": [item for item in downstreams if item],
            "_available_evidence": available_evidence,
            "_unavailable_evidence": unavailable,
        }
