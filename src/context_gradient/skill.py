"""DataHub Skill-compatible entrypoint for Predicate."""

from context_gradient.datahub.adapter import DataHubEvidenceExtractor, DataHubWriteback, GraphQLDataHubClient
from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.policy import load_policy


def certify(entity_urn: str, policy_path: str, datahub_url: str | None = None) -> dict:
    """Return a JSON-serializable certificate for a DataHub entity."""
    client = GraphQLDataHubClient(datahub_url)
    bundle = DataHubEvidenceExtractor(client).bundle(entity_urn)
    certificate = ReadinessEngine(load_policy(policy_path)).certify(bundle)
    return certificate.as_dict()


def certify_and_write(entity_urn: str, policy_path: str, datahub_url: str | None = None) -> dict:
    """Certify and publish through deployment-configured DataHub mutations."""
    client = GraphQLDataHubClient(datahub_url)
    bundle = DataHubEvidenceExtractor(client).bundle(entity_urn)
    certificate = ReadinessEngine(load_policy(policy_path)).certify(bundle)
    payload = certificate.as_dict()
    DataHubWriteback(client).publish(entity_urn, payload)
    return payload
