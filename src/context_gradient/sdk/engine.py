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
        # The policy file is the governing policy evidence for this run. It is
        # not expected to be duplicated as a dataset aspect in every DataHub.
        if not any(item.kind == EvidenceKind.POLICY and item.available for item in evidence):
            evidence = [item for item in evidence if item.kind != EvidenceKind.POLICY]
            evidence.append(
                EvidenceItem(
                    kind=EvidenceKind.POLICY,
                    present=True,
                    confidence=1.0,
                    details={"profile": self.policy.name, "source": "active_policy"},
                )
            )
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
                "score_semantics": "policy_weighted_evidence_summary",
                "score_note": (
                    "Readiness and confidence summarize the evidence observed in this run; "
                    "they are not model accuracy, data truth, or independent validation."
                ),
                "evidence_signals": len(evidence),
                "connected_assets": len(bundle.neighbors) + 1,
                "graph_coverage": score_trace["graph_coverage"],
                "score_trace": score_trace,
                "evidence_coverage": score_trace["evidence_coverage"],
                "assessment": profile,
                "datahub_observation": bundle.entity.properties.get("_datahub_observation", {}),
            },
        )

    def _normalize_staleness(self, evidence: Iterable[EvidenceItem]) -> List[EvidenceItem]:
        now = datetime.now(timezone.utc)
        normalized = []
        for item in evidence:
            max_age = self.policy.stale_after_days.get(item.kind)
            stale = item.stale
            age_seconds = max(0.0, (now - item.observed_at).total_seconds())
            # A fixture is a reproducible evidence snapshot. Its historical
            # timestamps are evidence values, not a promise that the demo
            # source was refreshed today. Do not let the calendar mutate a
            # fixture result; explicit stale/failing flags still block. Live
            # DataHub observations never carry this marker and continue to
            # age according to policy.
            is_reproducible_snapshot = item.details.get("freshness_semantics") == "reproducible_snapshot"
            if max_age is not None and age_seconds > max_age * 86400 and not is_reproducible_snapshot:
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
                    available=item.available,
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
            earned += weight * self._evidence_factor(item)
        return (earned / possible) * 100 if possible else 0.0

    def _propagate(self, score: float, bundle: EvidenceBundle) -> float:
        if not bundle.neighbors:
            return score
        neighbor_penalties = []
        for node in bundle.neighbors.values():
            usable = [item for item in node.evidence if item.available]
            # A connected neighbor without readable evidence is unknown, not
            # proven bad. Do not turn an API coverage gap into a score penalty.
            if not usable:
                continue
            weighted = 0.0
            possible = 0.0
            for item in node.evidence:
                weight = self.policy.evidence_weights.get(item.kind, 1.0)
                possible += weight
                weighted += weight * self._evidence_factor(item)
            if possible:
                neighbor_penalties.append(1.0 - (weighted / possible))
        if not neighbor_penalties:
            return score
        average_penalty = sum(neighbor_penalties) / len(neighbor_penalties)
        return max(0.0, score - (average_penalty * self.policy.graph_propagation * 100))

    def _confidence(self, evidence: List[EvidenceItem], bundle: EvidenceBundle) -> float:
        if not evidence:
            return 0.0
        usable = [item for item in evidence if item.available]
        if not usable:
            return 0.0
        # Unknown fields reduce confidence. They remain distinct from a
        # confirmed absence in the gaps, but a deployment that did not return
        # freshness or assertion results must not receive the same confidence
        # as a deployment that actually checked them.
        observed_fraction = len(usable) / len(evidence)
        coverage = sum(1 for item in usable if item.present) / len(evidence)
        quality = sum(item.confidence for item in usable) / len(usable)
        risk_rate = sum(1 for item in usable if item.contradictory or self._open_incident(item)) / len(usable)
        local_confidence = (coverage * 60) + (quality * observed_fraction * 40) - (risk_rate * 35)
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
            factor = self._evidence_factor(item)
            if not item.available:
                state = "unavailable"
            elif not item.present:
                state = "missing"
            elif self._open_incident(item):
                state = "open_incident"
            elif item.contradictory:
                state = "contradictory"
            elif item.stale:
                state = "stale"
            elif not item.complete:
                state = "incomplete"
            else:
                state = "present" if factor >= 1.0 else "present_thin"
            contribution = weight * factor
            earned += contribution
            rows.append({
                "evidence_kind": item.kind.value,
                "state": state,
                "present": item.present,
                "available": item.available,
                "complete": item.complete,
                "stale": item.stale,
                "contradictory": item.contradictory,
                    "confidence": round(item.confidence if item.available else 0.0, 4),
                "weight": round(weight, 4),
                "factor": factor,
                    "detail_quality": item.details.get("quality_factor", 1.0) if item.available else 0.0,
                "contribution": round(contribution, 4),
                "observed_at": item.observed_at.isoformat(),
                "details": item.details,
                "explanation": self._evidence_explanation(item, state),
            })
        expected_edges = len(bundle.entity.upstreams) + len(bundle.entity.downstreams)
        graph_coverage = 1.0 if expected_edges == 0 else min(1.0, len(bundle.neighbors) / expected_edges)
        usable = [item for item in evidence if item.available]
        coverage = sum(1 for item in usable if item.present) / len(evidence) if evidence else 0.0
        quality = sum(item.confidence for item in usable) / len(usable) if usable else 0.0
        contradictions = sum(1 for item in usable if item.contradictory) / len(usable) if usable else 0.0
        blocking_risk = sum(1 for item in usable if item.contradictory or self._open_incident(item)) / len(usable) if usable else 0.0
        return {
            "score_formula": "weighted evidence earned / weighted evidence possible * 100",
            "base_readiness_score": round(base_score, 2),
            "graph_adjustment": round(final_score - base_score, 2),
            "final_readiness_score": round(final_score, 2),
            "weighted_evidence_earned": round(earned, 4),
            "weighted_evidence_possible": round(possible, 4),
            "confidence_formula": "((coverage * 60) + (quality * observed fraction * 40) - (blocking risk * 35)) * graph factor",
            "coverage": round(coverage, 4),
            "average_source_confidence": round(quality, 4),
            "contradiction_rate": round(contradictions, 4),
            "blocking_risk_rate": round(blocking_risk, 4),
            "expected_graph_edges": expected_edges,
            "connected_graph_neighbors": len(bundle.neighbors),
            "graph_coverage": round(graph_coverage, 4),
            "evidence_coverage": {
                "total_signals": len(evidence),
                "observed_signals": len(usable),
                "unavailable_signals": [item.kind.value for item in evidence if not item.available],
                "confirmed_present": [item.kind.value for item in usable if item.present],
                "confirmed_absent": [item.kind.value for item in usable if not item.present],
                "interpretation": (
                    "complete observation"
                    if len(usable) == len(evidence)
                    else "partial observation; unavailable signals contribute zero readiness and cap confidence"
                ),
            },
            "evidence": rows,
        }

    @staticmethod
    def _evidence_explanation(item: EvidenceItem, state: str) -> str:
        """Give the reviewer one precise sentence about the observed state."""
        name = item.kind.value.replace("_", " ")
        details = item.details
        if state == "unavailable":
            return f"MetaGate could not read {name} from this DataHub response, so it is unknown rather than absent."
        if item.kind == EvidenceKind.ASSERTIONS:
            latest_results = details.get("latest_results") or details.get("results") or []
            passing = details.get("passing", 0)
            failing = details.get("failing", 0)
            unknown = details.get("unknown", 0)
            missing = len(details.get("missing_results", []))
            count = details.get("count")
            if count is None:
                count = len(latest_results) or sum(
                    int(value or 0) for value in (passing, failing, unknown)
                )
            if not count:
                return "No DataHub assertions were returned for this asset."
            if failing or unknown or missing:
                return f"DataHub returned {count} assertion(s): {passing} passed, {failing} failed, {unknown} unknown, and {missing} without a latest result."
            if not latest_results:
                return f"DataHub returned {count} assertion definition(s), but no latest run result was returned."
            return f"DataHub returned {count} assertion(s), and every latest run passed."
        if item.kind == EvidenceKind.FRESHNESS:
            if state == "missing":
                return "No freshness timestamp or freshness assertion was returned for this asset."
            return f"Freshness evidence was returned; its latest status is {'stale' if item.stale else 'current'}."
        if item.kind == EvidenceKind.LINEAGE:
            return f"DataHub returned {len(details.get('upstreams', []))} upstream and {len(details.get('downstreams', []))} downstream link(s)."
        if item.kind == EvidenceKind.COLUMN_LINEAGE:
            mapped = details.get("mapped_columns", 0)
            total = details.get("total_columns")
            missing = len(details.get("missing_columns", []))
            if total in (None, 0) and mapped:
                return f"Column lineage includes {mapped} mapped column(s); DataHub did not return a total schema-field count."
            return f"Column lineage covers {mapped} of {total or 0} schema field(s); {missing} remain unmapped."
        if item.kind == EvidenceKind.USAGE:
            buckets = details.get("buckets", [])
            if not buckets and details.get("weekly_users") is not None:
                return f"Usage evidence records {details['weekly_users']} weekly user(s) for this asset."
            return f"DataHub returned {len(buckets)} usage bucket(s), so downstream demand is {'observed' if buckets else 'not observed'}."
        if state == "missing":
            return f"DataHub responded successfully, but no {name} value was attached to the asset."
        if state == "stale":
            return f"A {name} value exists, but its timestamp is outside the active policy window."
        if state == "contradictory":
            return f"The {name} evidence conflicts with another signal or contains an active risk."
        if state == "incomplete":
            return f"The {name} value exists but does not contain all facts required by the policy."
        return f"DataHub returned current {name} evidence for this asset."

    def _evidence_factor(self, item: EvidenceItem) -> float:
        """Convert one evidence item into readiness credit.

        Unknown or unavailable evidence earns no credit. Assertions are stricter
        than ordinary metadata: a readable latest result is required, and any
        latest failure or unknown result earns zero credit.
        """
        if not item.available or not item.present:
            return 0.0
        if item.kind == EvidenceKind.ASSERTIONS:
            if item.details.get("failing", 0) or item.details.get("unknown", 0) or item.details.get("missing_results"):
                return 0.0
        if self._open_incident(item):
            return 0.0
        if item.contradictory:
            return 0.0
        if item.stale:
            return 0.45
        if not item.complete:
            return 0.0 if item.kind == EvidenceKind.ASSERTIONS else 0.65
        return self._quality_factor(item)

    def _gaps(self, evidence: List[EvidenceItem]) -> List[ReadinessGap]:
        gaps: List[ReadinessGap] = []
        for item in evidence:
            if not item.available:
                gaps.append(
                    self._gap(
                        GapType.UNAVAILABLE,
                        item.kind,
                        "unavailable from this DataHub deployment",
                        "Enable or configure the DataHub API surface for this evidence, then rerun MetaGate.",
                    )
                )
            elif self._open_incident(item):
                gaps.append(
                    self._gap(
                        GapType.CONTRADICTORY,
                        item.kind,
                        f"open ({item.details.get('open')} active)",
                        "Close or explicitly waive every open incident before allowing autonomous action.",
                    )
                )
            elif not item.present:
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
            if item.available and item.present and item.complete and not item.stale and not item.contradictory and not self._open_incident(item):
                claims.append(f"{item.kind.value} evidence is present and current.")
        return claims

    def _attach_gap_blocks(
        self, gaps: List[ReadinessGap], capabilities: List[CapabilityCertification], profile_required: List[str]
    ) -> List[ReadinessGap]:
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
                ),
            )
            for gap in gaps
        ]

    def _capabilities(
        self, score: float, confidence: float, evidence: List[EvidenceItem], profile_required: List[str]
    ) -> List[CapabilityCertification]:
        present: Set[EvidenceKind] = {
            item.kind
            for item in evidence
            if item.present and item.complete and not item.stale and not item.contradictory and not self._open_incident(item)
        }
        certifications = []
        for policy in self.policy.capability_policies:
            required = set(policy.required_evidence)
            if policy.name in {"generate-executive-metrics", "autonomous-agent-action"}:
                required.update(EvidenceKind(kind) for kind in profile_required)
            # Keep unavailable required evidence in the action score. It earns
            # no readiness credit and lowers confidence; dropping it here
            # would let a deployment silently certify an unchecked action.
            required_items = [item for item in evidence if item.kind in required]
            capability_score = self._score(required_items) if required_items else score
            capability_confidence = self._confidence_for_items(required_items) if required_items else confidence
            evidence_status = {
                kind.value: self._required_status(next((item for item in required_items if item.kind == kind), None))
                for kind in sorted(required, key=lambda item: item.value)
            }
            missing = [kind for kind, state in evidence_status.items() if state == "absent"]
            unavailable = [kind for kind, state in evidence_status.items() if state == "unavailable"]
            stale = [kind for kind, state in evidence_status.items() if state == "stale"]
            incomplete = [kind for kind, state in evidence_status.items() if state == "incomplete"]
            contradictory = [kind for kind, state in evidence_status.items() if state == "contradictory"]
            open_incidents = [kind for kind, state in evidence_status.items() if state == "open"]
            certified = (
                capability_score >= policy.minimum_score
                and capability_confidence >= policy.minimum_confidence
                and all(state == "present" for state in evidence_status.values())
            )
            reasons = []
            if missing:
                reasons.append("Missing required evidence: " + ", ".join(missing))
            if unavailable:
                reasons.append("Required evidence unavailable: " + ", ".join(unavailable))
            if stale:
                reasons.append("Required evidence stale: " + ", ".join(stale))
            if incomplete:
                reasons.append("Required evidence incomplete: " + ", ".join(incomplete))
            if contradictory:
                reasons.append("Contradictory required evidence: " + ", ".join(contradictory))
            if open_incidents:
                reasons.append("Open required incidents: " + ", ".join(open_incidents))
            if capability_score < policy.minimum_score:
                reasons.append(f"Readiness score below {policy.minimum_score}")
            if capability_confidence < policy.minimum_confidence:
                reasons.append(f"Confidence below {policy.minimum_confidence}")
            certifications.append(
                CapabilityCertification(
                    policy.name,
                    certified,
                    round(capability_score, 2),
                    round(capability_confidence, 2),
                    reasons,
                    sorted(evidence_status),
                    evidence_status,
                )
            )
        return certifications

    @classmethod
    def _required_status(cls, item: EvidenceItem | None) -> str:
        """Keep deployment unknowns distinct from a real metadata absence."""
        if item is None or not item.available:
            return "unavailable"
        if item.kind == EvidenceKind.INCIDENTS:
            return "open" if cls._open_incident(item) else ("present" if item.present else "absent")
        if item.contradictory:
            return "contradictory"
        if item.stale:
            return "stale"
        if not item.present:
            return "absent"
        if not item.complete:
            return "incomplete"
        if item.kind == EvidenceKind.ASSERTIONS and (
            item.details.get("failing", 0)
            or item.details.get("unknown", 0)
            or item.details.get("missing_results")
        ):
            return "contradictory"
        return "present"

    @staticmethod
    def _confidence_for_items(items: List[EvidenceItem]) -> float:
        usable = [item for item in items if item.available]
        if not usable:
            return 0.0
        coverage = sum(1 for item in usable if item.present) / len(items)
        observed_fraction = len(usable) / len(items)
        quality = sum(item.confidence for item in usable) / len(usable)
        risk = sum(1 for item in usable if item.contradictory) / len(usable)
        return max(0.0, min(100.0, (coverage * 60) + (quality * observed_fraction * 40) - (risk * 35)))

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

    @staticmethod
    def _open_incident(item: EvidenceItem) -> bool:
        if item.kind != EvidenceKind.INCIDENTS:
            return False
        open_count = item.details.get("open", 0)
        return isinstance(open_count, (int, float)) and open_count > 0

    @staticmethod
    def _quality_factor(item: EvidenceItem) -> float:
        """Use observed richness as a bounded refinement, not a second penalty system."""
        quality = item.details.get("quality_factor")
        if quality is None:
            return 1.0
        # A present signal remains meaningful; richness can refine it by up to 20%.
        return 0.8 + (0.2 * max(0.0, min(1.0, float(quality))))

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
