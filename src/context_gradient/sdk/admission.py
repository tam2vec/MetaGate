from __future__ import annotations

from context_gradient.sdk.models import AdmissionDecision, ReadinessCertificate


def admit_capability(certificate: ReadinessCertificate | dict, capability: str) -> AdmissionDecision:
    """Make the final deterministic allow/block decision for an agent action."""
    payload = certificate.as_dict() if hasattr(certificate, "as_dict") else certificate
    allowed = capability in payload["context_contract"]["allowed_capabilities"]
    matching = next((item for item in payload["certified_capabilities"] if item["capability"] == capability), None)
    if allowed:
        return AdmissionDecision(payload["entity_urn"], capability, True, "Capability is certified by the active policy.", payload["context_contract"].get("verified_claims", []))
    reason = "; ".join((matching or {}).get("reasons", [])) or "Capability is not certified by the active policy."
    return AdmissionDecision(payload["entity_urn"], capability, False, reason, payload["context_contract"].get("verified_claims", []))
