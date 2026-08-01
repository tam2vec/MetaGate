from __future__ import annotations

from typing import Any, Dict

from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.models import EvidenceBundle, ReadinessCertificate
from context_gradient.sdk.policy import PolicyProfile


def simulate_policy(bundle: EvidenceBundle, current: PolicyProfile, proposed: PolicyProfile) -> Dict[str, Any]:
    """Compare certifications without mutating history or DataHub."""
    before = ReadinessEngine(current).certify(bundle)
    after = ReadinessEngine(proposed).certify(bundle)
    before_allowed = {item.capability for item in before.certified_capabilities if item.certified}
    after_allowed = {item.capability for item in after.certified_capabilities if item.certified}
    return {
        "entity_urn": bundle.entity.urn,
        "current_policy": current.name,
        "proposed_policy": proposed.name,
        "current_score": before.readiness_score,
        "proposed_score": after.readiness_score,
        "newly_blocked": sorted(before_allowed - after_allowed),
        "newly_certified": sorted(after_allowed - before_allowed),
        "current_certificate": before.as_dict(),
        "proposed_certificate": after.as_dict(),
    }
