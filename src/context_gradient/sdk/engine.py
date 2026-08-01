from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, List, Set

from context_gradient.sdk.models import (
    CapabilityCertification,
    ContextContract,
    EvidenceBundle,
    EvidenceItem,
    EvidenceKind,
    GapType,
    ReadinessCertificate,
    ReadinessGap,
)
from context_gradient.sdk.assessment import assessment
from context_gradient.sdk.policy import PolicyProfile


class ReadinessEngine:
    def __init__(self, policy: PolicyProfile):
        self.policy = policy

    def certify(self, bundle: EvidenceBundle) -> ReadinessCertificate:
        evidence = self._normalize_staleness(bundle.items())
        score = self._score(evidence)
        propagated_score = self._propagate(score, bundle)
        confidence = self._confidence(evidence, bundle)
        gaps = self._gaps(evidence)
        profile = assessment(bundle)
        profile_required = profile["required_evidence"]
        capabilities = self._capabilities(propagated_score, confidence, evidence, profile_required)
        gaps = self._attach_gap_blocks(gaps, capabilities, profile_required)
        allowed = [cap.capability for cap in capabilities if cap.certified]
        blocked = [cap.capability for cap in capabilities if not cap.certified]
        recommendations = self._recommendations(gaps, capabilities)
        contract = ContextContract(
            entity_urn=bundle.entity.urn,
            allowed_capabilities=allowed,
            blocked_capabilities=blocked,
            required_controls=sorted({gap.evidence_kind.value for gap in gaps}),
            evidence_summary=self._summary(evidence),
            policy=self.policy.name,
            verified_claims=self._verified_claims(evidence),
            forbidden_claims=[f"Do not claim {cap.capability} is safe." for cap in capabilities if not cap.certified],
            required_escalations=[
                {"capability": cap.capability, "reason": "; ".join(cap.reasons)}
                for cap in capabilities if not cap.certified
            ],
        )
        score_trace = self._score_trace(evidence, bundle, score, propagated_score)
        return ReadinessCertificate(
            entity_urn=bundle.entity.urn,
            readiness_score=round(propagated_score, 2),
            confidence=round(confidence, 2),
            business_impact=self._business_impact(propagated_score, blocked),
            certified_capabilities=capabilities,
            gaps=gaps,
            recommendations=recommendations,
            context_contract=contract,
            metadata={
                "policy": self.policy.name,
                "evidence_signals": len(evidence),
                "connected_assets": len(bundle.neighbors) + 1,
                "graph_coverage": score_trace["graph_coverage"],
                "score_trace": score_trace,
                "assessment": profile,
            },
        )

    def _normalize_staleness(self, evidence: Iterable[EvidenceItem]) -> List[EvidenceItem]:
        now = datetime.now(timezone.utc)
        normalized = []
        for item in evidence:
            max_age = self.policy.stale_after_days.get(item.kind)
            stale = item.stale
            age_seconds = max(0.0, (now - item.observed_at).total_seconds())
            if max_age is not None and age_seconds > max_age * 86400:
                stale = True
            normalized.append(
                EvidenceItem(
                    kind=item.kind,
                    present=item.present,
                    complete=item.complete,
                    stale=stale,
                    contradictory=item.contradictory,
                    confidence=item.confidence,
                    weight=item.weight,
                    observed_at=item.observed_at,
                    details=item.details,
                )
            )
        return normalized

    def _score(self, evidence: List[EvidenceItem]) -> float:
        if not evidence:
            return 0.0
        earned = 0.0
        possible = 0.0
        for item in evidence:
            weight = self.policy.evidence_weights.get(item.kind, 1.0) * item.weight
            possible += weight
            factor = 1.0
            if not item.present:
                factor = 0.0
            elif item.contradictory:
                factor = 0.2
            elif item.stale:
                factor = 0.45
            elif not item.complete:
                factor = 0.65
            earned += weight * factor
        return (earned / possible) * 100 if possible else 0.0

    def _propagate(self, score: float, bundle: EvidenceBundle) -> float:
        if not bundle.neighbors:
            return score
        neighbor_penalties = []
        for node in bundle.neighbors.values():
            if not node.evidence:
                neighbor_penalties.append(1.0)
                continue
            weighted = 0.0
            possible = 0.0
            for item in node.evidence:
                weight = self.policy.evidence_weights.get(item.kind, 1.0)
                possible += weight
                factor = 0.0 if not item.present else 0.2 if item.contradictory else 0.45 if item.stale else 0.65 if not item.complete else 1.0
                weighted += weight * factor
            neighbor_penalties.append(1.0 - (weighted / possible if possible else 0.0))
        average_penalty = sum(neighbor_penalties) / len(neighbor_penalties)
        return max(0.0, score - (average_penalty * self.policy.graph_propagation * 100))

    def _confidence(self, evidence: List[EvidenceItem], bundle: EvidenceBundle) -> float:
        if not evidence:
            return 0.0
        coverage = sum(1 for item in evidence if item.present) / len(evidence)
        quality = sum(item.confidence for item in evidence) / len(evidence)
        contradictions = sum(1 for item in evidence if item.contradictory) / len(evidence)
        local_confidence = (coverage * 60) + (quality * 40) - (contradictions * 35)
        expected_edges = len(bundle.entity.upstreams) + len(bundle.entity.downstreams)
        graph_coverage = 1.0 if expected_edges == 0 else min(1.0, len(bundle.neighbors) / expected_edges)
        return max(0.0, min(100.0, local_confidence * (0.75 + (0.25 * graph_coverage))))

    def _score_trace(
        self,
        evidence: List[EvidenceItem],
        bundle: EvidenceBundle,
        base_score: float,
        final_score: float,
    ) -> dict:
        """Expose the evidence math behind a certificate for audit and UI use."""
        rows = []
        possible = 0.0
        earned = 0.0
        for item in evidence:
            weight = self.policy.evidence_weights.get(item.kind, 1.0) * item.weight
            possible += weight
            factor = 1.0
            state = "present"
            if not item.present:
                factor, state = 0.0, "missing"
            elif item.contradictory:
                factor, state = 0.2, "contradictory"
            elif item.stale:
                factor, state = 0.45, "stale"
            elif not item.complete:
                factor, state = 0.65, "incomplete"
            contribution = weight * factor
            earned += contribution
            rows.append({
                "evidence_kind": item.kind.value,
                "state": state,
                "present": item.present,
                "complete": item.complete,
                "stale": item.stale,
                "contradictory": item.contradictory,
                "confidence": round(item.confidence, 4),
                "weight": round(weight, 4),
                "factor": factor,
                "contribution": round(contribution, 4),
                "observed_at": item.observed_at.isoformat(),
                "details": item.details,
            })
        expected_edges = len(bundle.entity.upstreams) + len(bundle.entity.downstreams)
        graph_coverage = 1.0 if expected_edges == 0 else min(1.0, len(bundle.neighbors) / expected_edges)
        coverage = sum(1 for item in evidence if item.present) / len(evidence) if evidence else 0.0
        quality = sum(item.confidence for item in evidence) / len(evidence) if evidence else 0.0
        contradictions = sum(1 for item in evidence if item.contradictory) / len(evidence) if evidence else 0.0
        return {
            "score_formula": "weighted evidence earned / weighted evidence possible * 100",
            "base_readiness_score": round(base_score, 2),
            "graph_adjustment": round(final_score - base_score, 2),
            "final_readiness_score": round(final_score, 2),
            "weighted_evidence_earned": round(earned, 4),
            "weighted_evidence_possible": round(possible, 4),
            "confidence_formula": "((coverage * 60) + (quality * 40) - (contradictions * 35)) * graph factor",
            "coverage": round(coverage, 4),
            "average_source_confidence": round(quality, 4),
            "contradiction_rate": round(contradictions, 4),
            "expected_graph_edges": expected_edges,
            "connected_graph_neighbors": len(bundle.neighbors),
            "graph_coverage": round(graph_coverage, 4),
            "evidence": rows,
        }

    def _gaps(self, evidence: List[EvidenceItem]) -> List[ReadinessGap]:
        gaps: List[ReadinessGap] = []
        for item in evidence:
            if not item.present:
                gaps.append(
                    self._gap(
                        GapType.MISSING,
                        item.kind,
                        "missing",
                        self._recommendation_for(item.kind, GapType.MISSING),
                    )
                )
            elif item.contradictory:
                gaps.append(
                    self._gap(
                        GapType.CONTRADICTORY,
                        item.kind,
                        "contradictory",
                        self._recommendation_for(item.kind, GapType.CONTRADICTORY),
                    )
                )
            elif item.stale:
                gaps.append(
                    self._gap(
                        GapType.STALE,
                        item.kind,
                        "stale",
                        self._recommendation_for(item.kind, GapType.STALE),
                    )
                )
            elif not item.complete:
                gaps.append(
                    self._gap(
                        GapType.INCOMPLETE,
                        item.kind,
                        "incomplete",
                        self._recommendation_for(item.kind, GapType.INCOMPLETE),
                    )
                )
        return gaps

    def _recommendation_for(self, kind: EvidenceKind, gap_type: GapType) -> str:
        base = {
            EvidenceKind.DESCRIPTION: "Add a business-readable asset description with purpose, grain, and known limitations.",
            EvidenceKind.OWNERSHIP: "Assign an accountable business owner and technical owner before allowing high-impact AI actions.",
            EvidenceKind.GLOSSARY: "Attach approved glossary terms for core business concepts used by this asset.",
            EvidenceKind.DOMAIN: "Assign the asset to the owning DataHub domain so escalation and policy routing are clear.",
            EvidenceKind.TAGS: "Add governance tags such as production, pii, restricted, or pii-free as appropriate.",
            EvidenceKind.LINEAGE: "Register upstream and downstream lineage so the agent can reason about blast radius.",
            EvidenceKind.COLUMN_LINEAGE: "Map column-level lineage for fields the agent may summarize, transform, or modify.",
            EvidenceKind.ASSERTIONS: "Add passing DataHub assertions or equivalent quality checks for freshness, row counts, nulls, and key business invariants.",
            EvidenceKind.INCIDENTS: "Close or explicitly waive open incidents before allowing autonomous action.",
            EvidenceKind.FRESHNESS: "Refresh the source or update the freshness SLA evidence before relying on this asset.",
            EvidenceKind.USAGE: "Add usage evidence or consumer telemetry so the system can estimate downstream impact.",
            EvidenceKind.DASHBOARDS: "Link dependent dashboards to reveal executive or operational reporting impact.",
            EvidenceKind.CHARTS: "Link dependent charts so reporting blast radius is visible.",
            EvidenceKind.ML_MODELS: "Link dependent ML models before allowing changes that may affect features or training data.",
            EvidenceKind.DOWNSTREAM_CONSUMERS: "Register downstream consumers and owners before allowing autonomous changes.",
            EvidenceKind.POLICY: "Attach the active policy profile that defines which AI actions are allowed for this asset.",
        }
        action = base.get(kind, "Repair the metadata evidence required by the active policy.")
        if gap_type == GapType.CONTRADICTORY:
            return f"Resolve conflicting {kind.value} sources, pick the authoritative DataHub value, then rerun certification."
        if gap_type == GapType.STALE:
            return f"Refresh stale {kind.value} evidence and verify the update timestamp is inside the policy window."
        if gap_type == GapType.INCOMPLETE:
            return f"Complete partial {kind.value} evidence: {action}"
        return action

    def _gap(
        self, gap_type: GapType, kind: EvidenceKind, adjective: str, recommendation: str
    ) -> ReadinessGap:
        severity = "high" if gap_type in {GapType.MISSING, GapType.CONTRADICTORY} else "medium"
        return ReadinessGap(
            type=gap_type,
            evidence_kind=kind,
            message=f"{kind.value} evidence is {adjective}.",
            severity=severity,
            recommendation=recommendation,
        )

    def _verified_claims(self, evidence: List[EvidenceItem]) -> List[str]:
        claims = []
        for item in evidence:
            if item.present and item.complete and not item.stale and not item.contradictory:
                claims.append(f"{item.kind.value} evidence is present and current.")
        return claims

    def _attach_gap_blocks(
        self, gaps: List[ReadinessGap], capabilities: List[CapabilityCertification], profile_required: List[str]
    ) -> List[ReadinessGap]:
        blocked = {cap.capability for cap in capabilities if not cap.certified}
        return [
            ReadinessGap(
                type=gap.type,
                evidence_kind=gap.evidence_kind,
                message=gap.message,
                severity=gap.severity,
                recommendation=gap.recommendation,
                evidence=[gap.message],
                blocks=sorted(
                    cap.name
                    for cap in self.policy.capability_policies
                    if not next(item for item in capabilities if item.capability == cap.name).certified
                    and (
                        gap.evidence_kind in cap.required_evidence
                        or (cap.name in {"generate-executive-metrics", "autonomous-agent-action"}
                            and gap.evidence_kind.value in profile_required)
                    )
                ) or sorted(blocked),
            )
            for gap in gaps
        ]

    def _capabilities(
        self, score: float, confidence: float, evidence: List[EvidenceItem], profile_required: List[str]
    ) -> List[CapabilityCertification]:
        present: Set[EvidenceKind] = {
            item.kind
            for item in evidence
            if item.present and item.complete and not item.stale and not item.contradictory
        }
        certifications = []
        for policy in self.policy.capability_policies:
            required = set(policy.required_evidence)
            if policy.name in {"generate-executive-metrics", "autonomous-agent-action"}:
                required.update(EvidenceKind(kind) for kind in profile_required)
            missing = [kind.value for kind in sorted(required, key=lambda item: item.value) if kind not in present]
            certified = (
                score >= policy.minimum_score
                and confidence >= policy.minimum_confidence
                and not missing
            )
            reasons = []
            if missing:
                reasons.append("Missing required evidence: " + ", ".join(missing))
            if score < policy.minimum_score:
                reasons.append(f"Readiness score below {policy.minimum_score}")
            if confidence < policy.minimum_confidence:
                reasons.append(f"Confidence below {policy.minimum_confidence}")
            certifications.append(
                CapabilityCertification(policy.name, certified, round(score, 2), round(confidence, 2), reasons)
            )
        return certifications

    def _recommendations(
        self, gaps: List[ReadinessGap], capabilities: List[CapabilityCertification]
    ) -> List[str]:
        recommendations = []
        for gap in gaps:
            recommendations.append(f"{gap.recommendation} ({gap.evidence_kind.value})")
        for cap in capabilities:
            if not cap.certified:
                recommendations.append(f"Unlock {cap.capability}: " + "; ".join(cap.reasons))
        return list(dict.fromkeys(recommendations))

    def _summary(self, evidence: List[EvidenceItem]) -> dict:
        return {
            item.kind.value: {
                "present": item.present,
                "complete": item.complete,
                "stale": item.stale,
                "contradictory": item.contradictory,
                "confidence": item.confidence,
            }
            for item in evidence
        }

    def _business_impact(self, score: float, blocked: List[str]) -> str:
        if score >= self.policy.minimum_score and not blocked:
            return "AI use is cleared for certified capabilities."
        if score >= 60:
            return "AI use is partially blocked until listed gaps are remediated."
        return "AI use should remain blocked for high-impact automated decisions."
