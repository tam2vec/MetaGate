from __future__ import annotations

from context_gradient.sdk.models import ReadinessCertificate, ReadinessDiff


def diff_certificates(
    previous: ReadinessCertificate | dict | None, current: ReadinessCertificate
) -> ReadinessDiff:
    current_certified = {
        cap.capability for cap in current.certified_capabilities if cap.certified
    }
    current_blocked = {
        cap.capability for cap in current.certified_capabilities if not cap.certified
    }
    current_gaps = {gap.message for gap in current.gaps}
    if previous is None:
        return ReadinessDiff(
            entity_urn=current.entity_urn,
            previous_score=None,
            current_score=current.readiness_score,
            score_delta=None,
            newly_certified=sorted(current_certified),
            newly_blocked=sorted(current_blocked),
            new_gaps=sorted(current_gaps),
            resolved_gaps=[],
        )

    caps = previous["certified_capabilities"] if isinstance(previous, dict) else previous.certified_capabilities
    previous_certified = {cap["capability"] for cap in caps if cap["certified"]} if isinstance(previous, dict) else {cap.capability for cap in caps if cap.certified}
    previous_blocked = {cap["capability"] for cap in caps if not cap["certified"]} if isinstance(previous, dict) else {cap.capability for cap in caps if not cap.certified}
    gaps = previous["gaps"] if isinstance(previous, dict) else previous.gaps
    previous_gaps = {gap["message"] for gap in gaps} if isinstance(previous, dict) else {gap.message for gap in gaps}
    return ReadinessDiff(
        entity_urn=current.entity_urn,
        previous_score=previous["readiness_score"] if isinstance(previous, dict) else previous.readiness_score,
        current_score=current.readiness_score,
        score_delta=round(current.readiness_score - (previous["readiness_score"] if isinstance(previous, dict) else previous.readiness_score), 2),
        newly_certified=sorted(current_certified - previous_certified),
        newly_blocked=sorted(current_blocked - previous_blocked),
        new_gaps=sorted(current_gaps - previous_gaps),
        resolved_gaps=sorted(previous_gaps - current_gaps),
    )
