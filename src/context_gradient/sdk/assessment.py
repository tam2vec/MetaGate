from __future__ import annotations

from typing import Any, Dict, Iterable

from context_gradient.sdk.models import EvidenceBundle, EvidenceItem, EvidenceKind


RUBRIC_DEFINITIONS: Dict[str, Dict[str, str]] = {
    "assertions": {
        "meaning": "DataHub has named quality checks for this asset with a latest result.",
        "passes_when": "At least one check is present, its latest result is readable, and no required check is failing or contradictory.",
        "fails_when": "No assertion is returned, the result is stale or failing, or the checks do not cover the asset's important fields.",
    },
    "freshness": {
        "meaning": "DataHub can show when this asset was last updated and whether it met its freshness expectation.",
        "passes_when": "A timestamp or freshness result is present, current for the active policy, and not marked stale.",
        "fails_when": "No timestamp is available, the asset is outside its freshness window, or the freshness result is stale.",
    },
    "lineage": {
        "meaning": "DataHub can show where the asset came from and what depends on it.",
        "passes_when": "The expected upstream and downstream links are present and the important paths are not marked incomplete.",
        "fails_when": "Lineage is empty when it is required, incomplete, or missing the links needed to understand impact.",
    },
    "column_lineage": {
        "meaning": "DataHub can trace important columns back to their sources.",
        "passes_when": "Required fields have mappings from source to destination and no important columns are left unmapped.",
        "fails_when": "Mappings are absent, incomplete, or do not cover the columns used by the requested action.",
    },
}


PROFILE_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "kafka_stream": {
        "label": "Kafka stream",
        "match": "Kafka platform or stream-like asset",
        "required_evidence": ["ownership", "lineage", "assertions", "freshness", "incidents"],
        "checks": [
            ("assertions", "schema compatibility, payload parse failures, and consumer lag are checked"),
            ("freshness", "latest events arrive within the stream SLA"),
            ("incidents", "open delivery or consumer incidents are reviewed"),
        ],
        "guidance": "Add stream-specific checks for schema compatibility, lag, parse failures, and event freshness before allowing automated action.",
    },
    "finance_table": {
        "label": "Finance table",
        "match": "Finance domain or finance-like asset",
        "required_evidence": ["ownership", "glossary", "lineage", "column_lineage", "assertions", "freshness", "policy"],
        "checks": [
            ("glossary", "currency, revenue, and metric definitions are explicit"),
            ("column_lineage", "money-making fields trace to approved sources"),
            ("assertions", "non-negative, currency, reconciliation, and date checks are passing"),
        ],
        "guidance": "Resolve metric definitions first, then add reconciliation, currency, non-negative-value, and reporting-date checks with an accountable owner.",
    },
    "ml_feature": {
        "label": "ML feature dataset",
        "match": "Feature or model-serving asset",
        "required_evidence": ["ownership", "lineage", "column_lineage", "assertions", "freshness", "policy"],
        "checks": [
            ("column_lineage", "features trace to source fields and transformations"),
            ("freshness", "features are available before the serving cutoff"),
            ("assertions", "null, range, drift, and training-serving consistency checks are passing"),
        ],
        "guidance": "Document feature origins and add null, range, drift, and training-serving consistency checks before an agent can use the features.",
    },
    "geospatial_dataset": {
        "label": "Geospatial dataset",
        "match": "Geospatial asset",
        "required_evidence": ["ownership", "glossary", "lineage", "column_lineage", "assertions", "freshness"],
        "checks": [
            ("glossary", "coordinate reference system and geographic meaning are defined"),
            ("assertions", "geometry validity, bounds, and duplicate-location checks are passing"),
            ("column_lineage", "geometry and location fields trace to their sources"),
        ],
        "guidance": "Define the coordinate system and geographic meaning, then validate geometry, bounds, duplicates, and location-field lineage.",
    },
    "analytics_table": {
        "label": "Analytics table",
        "match": "Default analytical dataset",
        "required_evidence": ["ownership", "glossary", "lineage", "assertions", "freshness"],
        "checks": [
            ("glossary", "business terms explain what the table and its key fields mean"),
            ("assertions", "key, volume, and freshness checks are passing"),
            ("lineage", "upstream source and downstream impact are visible"),
        ],
        "guidance": "Assign an owner, define key terms, document upstream and downstream use, and add checks for keys, volume, and freshness.",
    },
}


def dataset_profile(urn: str, entity_properties: Dict[str, Any] | None = None) -> str:
    value = f"{urn} {entity_properties or {}}".lower()
    if "kafka" in value or "stream" in value or "topic" in value:
        return "kafka_stream"
    if any(term in value for term in ("finance", "revenue", "lifetime_value", "arr", "billing")):
        return "finance_table"
    if any(term in value for term in ("feature", "model", "embedding", "prediction")):
        return "ml_feature"
    if any(term in value for term in ("geo", "location", "latitude", "longitude", "polygon")):
        return "geospatial_dataset"
    return "analytics_table"


def _kind_map(items: Iterable[EvidenceItem]) -> Dict[EvidenceKind, EvidenceItem]:
    return {item.kind: item for item in items}


def _fact_value(details: Dict[str, Any], keys: tuple[str, ...], default: Any = None) -> Any:
    for key in keys:
        if key in details:
            return details[key]
    return default


def evidence_facts(bundle: EvidenceBundle) -> Dict[str, Any]:
    items = _kind_map(bundle.entity.evidence)
    def details(kind: EvidenceKind) -> Dict[str, Any]:
        value = items.get(kind)
        return value.details if value else {}

    owner = details(EvidenceKind.OWNERSHIP)
    glossary = details(EvidenceKind.GLOSSARY)
    lineage = details(EvidenceKind.LINEAGE)
    columns = details(EvidenceKind.COLUMN_LINEAGE)
    assertions = details(EvidenceKind.ASSERTIONS)
    freshness = details(EvidenceKind.FRESHNESS)
    return {
        "owner": _fact_value(owner, ("owners", "owner", "owner_urn"), []),
        "glossary_terms": _fact_value(glossary, ("terms", "term_urns"), []),
        "lineage": {
            "upstream_count": len(_fact_value(lineage, ("upstreams",), []) or []),
            "downstream_count": len(bundle.entity.downstreams),
            "upstreams": _fact_value(lineage, ("upstreams",), []),
            "downstreams": bundle.entity.downstreams,
        },
        "column_lineage": {
            "mapping_count": _fact_value(columns, ("mapped_columns", "mapping_count"), len(_fact_value(columns, ("mappings",), []) or [])),
            "missing_columns": _fact_value(columns, ("missing_columns", "unmapped_columns"), []),
        },
        "assertions": {
            "count": _fact_value(assertions, ("count",), 0),
            "passing": _fact_value(assertions, ("passing", "passed"), None),
            "failing": _fact_value(assertions, ("failing", "failed"), None),
            "names": _fact_value(assertions, ("names", "assertion_names"), []),
            "latest_results": _fact_value(assertions, ("latest_results", "results", "latest_result"), []),
        },
        "freshness": {
            "observed_at": freshness.get("observed_at"),
            "timestamp": _fact_value(freshness, ("timestamp", "last_updated", "last_updated_at")),
            "minutes_late": freshness.get("minutes_late"),
            "stale": freshness.get("stale", False),
        },
    }


def assessment(bundle: EvidenceBundle) -> Dict[str, Any]:
    profile_key = dataset_profile(bundle.entity.urn, bundle.entity.properties)
    profile = PROFILE_DEFINITIONS[profile_key]
    item_map = _kind_map(bundle.entity.evidence)
    checks = []
    for kind, explanation in profile["checks"]:
        item = item_map.get(EvidenceKind(kind))
        checks.append({
            "evidence_kind": kind,
            "status": "pass" if item and item.present and item.complete and not item.stale and not item.contradictory else "needs attention",
            "check": explanation,
        })
    return {
        "profile": profile_key,
        "profile_label": profile["label"],
        "profile_match": profile["match"],
        "required_evidence": profile["required_evidence"],
        "rubric": {key: RUBRIC_DEFINITIONS[key] for key in profile["required_evidence"] if key in RUBRIC_DEFINITIONS},
        "checks": checks,
        "guidance": profile["guidance"],
        "facts": evidence_facts(bundle),
    }
