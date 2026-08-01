from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.admission import admit_capability
from context_gradient.sdk.reports import explain_certificate
from context_gradient.sdk.simulation import simulate_policy


def evaluate_asset(entity_urn, policy, client):
    """Evaluate one asset through any DataHubClient-compatible adapter."""
    from context_gradient.datahub.adapter import DataHubEvidenceExtractor
    return ReadinessEngine(policy).certify(DataHubEvidenceExtractor(client).bundle(entity_urn))


def generate_context_contract(certificate):
    payload = certificate.as_dict() if hasattr(certificate, "as_dict") else certificate
    return payload["context_contract"]
from context_gradient.sdk.models import (
    CapabilityCertification,
    ContextContract,
    EvidenceBundle,
    ReadinessCertificate,
    ReadinessGap,
)
from context_gradient.sdk.policy import PolicyProfile, load_policy

__all__ = [
    "CapabilityCertification",
    "ContextContract",
    "EvidenceBundle",
    "PolicyProfile",
    "ReadinessCertificate",
    "ReadinessEngine",
    "ReadinessGap",
    "load_policy",
    "admit_capability",
    "evaluate_asset",
    "explain_certificate",
    "generate_context_contract",
    "simulate_policy",
]
