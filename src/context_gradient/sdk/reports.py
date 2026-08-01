from __future__ import annotations

from typing import Any, Dict

from context_gradient.sdk.models import ReadinessCertificate


def explain_certificate(certificate: ReadinessCertificate | dict) -> Dict[str, Any]:
    """Return an inspectable evidence -> policy -> decision report."""
    payload = certificate.as_dict() if hasattr(certificate, "as_dict") else certificate
    return {
        "entity_urn": payload["entity_urn"],
        "policy": payload["metadata"].get("policy", payload["context_contract"].get("policy", "default")),
        "readiness_score": payload["readiness_score"],
        "confidence": payload["confidence"],
        "decisions": [
            {
                "capability": capability["capability"],
                "decision": "allowed" if capability["certified"] else "blocked",
                "policy_thresholds": {"score": capability["score"], "confidence": capability["confidence"]},
                "reasons": capability.get("reasons", []),
                "affected_gaps": [gap for gap in payload["gaps"] if capability["capability"] in gap.get("blocks", [])],
            }
            for capability in payload["certified_capabilities"]
        ],
        "graph": {
            "connected_assets": payload["metadata"].get("connected_assets", 1),
            "evidence_signals": payload["metadata"].get("evidence_signals", 0),
        },
        "score_trace": payload["metadata"].get("score_trace", {}),
    }
