from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GapType(str, Enum):
    MISSING = "missing"
    UNAVAILABLE = "unavailable"
    STALE = "stale"
    INCOMPLETE = "incomplete"
    CONTRADICTORY = "contradictory"


class EvidenceKind(str, Enum):
    DESCRIPTION = "description"
    OWNERSHIP = "ownership"
    GLOSSARY = "glossary"
    DOMAIN = "domain"
    TAGS = "tags"
    LINEAGE = "lineage"
    COLUMN_LINEAGE = "column_lineage"
    ASSERTIONS = "assertions"
    INCIDENTS = "incidents"
    FRESHNESS = "freshness"
    USAGE = "usage"
    DASHBOARDS = "dashboards"
    CHARTS = "charts"
    ML_MODELS = "ml_models"
    DOWNSTREAM_CONSUMERS = "downstream_consumers"
    POLICY = "policy"


@dataclass(frozen=True)
class EvidenceItem:
    kind: EvidenceKind
    present: bool
    complete: bool = True
    stale: bool = False
    contradictory: bool = False
    confidence: float = 1.0
    weight: float = 1.0
    observed_at: datetime = field(default_factory=utc_now)
    details: Dict[str, Any] = field(default_factory=dict)
    available: bool = True


@dataclass(frozen=True)
class EntityNode:
    urn: str
    type: str = "dataset"
    properties: Dict[str, Any] = field(default_factory=dict)
    evidence: List[EvidenceItem] = field(default_factory=list)
    upstreams: List[str] = field(default_factory=list)
    downstreams: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class EvidenceBundle:
    entity: EntityNode
    neighbors: Dict[str, EntityNode] = field(default_factory=dict)

    def items(self) -> List[EvidenceItem]:
        return list(self.entity.evidence)


@dataclass(frozen=True)
class ReadinessGap:
    type: GapType
    evidence_kind: EvidenceKind
    message: str
    severity: str
    recommendation: str
    evidence: List[str] = field(default_factory=list)
    blocks: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class CapabilityCertification:
    capability: str
    certified: bool
    score: float
    confidence: float
    reasons: List[str] = field(default_factory=list)
    required_evidence: List[str] = field(default_factory=list)
    evidence_status: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ContextContract:
    entity_urn: str
    allowed_capabilities: List[str]
    blocked_capabilities: List[str]
    required_controls: List[str]
    evidence_summary: Dict[str, Any]
    generated_at: datetime = field(default_factory=utc_now)
    policy: str = "default"
    verified_claims: List[str] = field(default_factory=list)
    forbidden_claims: List[str] = field(default_factory=list)
    required_escalations: List[Dict[str, str]] = field(default_factory=list)
    valid_until_event: str = "Any relevant DataHub metadata graph change"


@dataclass(frozen=True)
class ReadinessCertificate:
    entity_urn: str
    readiness_score: float
    confidence: float
    business_impact: str
    certified_capabilities: List[CapabilityCertification]
    gaps: List[ReadinessGap]
    recommendations: List[str]
    context_contract: ContextContract
    issued_at: datetime = field(default_factory=utc_now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        def convert(value: Any) -> Any:
            if isinstance(value, datetime):
                return value.isoformat()
            if isinstance(value, Enum):
                return value.value
            if hasattr(value, "__dataclass_fields__"):
                return {k: convert(getattr(value, k)) for k in value.__dataclass_fields__}
            if isinstance(value, list):
                return [convert(v) for v in value]
            if isinstance(value, dict):
                return {k: convert(v) for k, v in value.items()}
            return value

        return convert(self)


@dataclass(frozen=True)
class ReadinessDiff:
    entity_urn: str
    previous_score: Optional[float]
    current_score: float
    score_delta: Optional[float]
    newly_certified: List[str]
    newly_blocked: List[str]
    new_gaps: List[str]
    resolved_gaps: List[str]


@dataclass(frozen=True)
class AdmissionDecision:
    entity_urn: str
    capability: str
    allowed: bool
    reason: str
    evidence: List[str] = field(default_factory=list)
    escalation_owner: Optional[str] = None
