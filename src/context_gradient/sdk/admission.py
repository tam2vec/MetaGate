from __future__ import annotations

from context_gradient.sdk.models import AdmissionDecision, ReadinessCertificate


HIGH_RISK_ACTIONS = {
    "generate-executive-metrics",
    "autonomous-agent-action",
    "modify-dataset",
    "restricted-sql",
}


def _payload(certificate: ReadinessCertificate | dict) -> dict:
    return certificate.as_dict() if hasattr(certificate, "as_dict") else certificate


def _facts(payload: dict) -> dict:
    metadata = payload.get("metadata") or {}
    assessment = metadata.get("assessment") or {}
    facts = assessment.get("facts") or payload.get("facts") or {}
    return facts if isinstance(facts, dict) else {}


def _latest_assertions(facts: dict) -> list[dict]:
    assertions = facts.get("assertions") or {}
    results = assertions.get("latest_results") or assertions.get("latest_result") or []
    if isinstance(results, dict):
        results = [results]
    latest: dict[str, dict] = {}
    for index, item in enumerate(results):
        if not isinstance(item, dict):
            continue
        key = str(item.get("assertion_urn") or item.get("assertion_name") or item.get("name") or item.get("urn") or index)
        current = latest.get(key)
        if current is None or _observation_key(item) >= _observation_key(current):
            latest[key] = item
    return list(latest.values())


def _observation_key(item: dict) -> tuple:
    value = item.get("observed_at") or item.get("timestamp") or item.get("timestampMillis") or item.get("created_at") or ""
    try:
        return (0, int(value))
    except (TypeError, ValueError):
        return (1, str(value))


def _assertion_failed(result: dict) -> bool:
    value = result.get("result", result.get("status", result.get("state")))
    if isinstance(value, bool):
        return not value
    normalized = str(value or "").strip().lower()
    return normalized in {"fail", "failed", "failure", "error", "errored", "failing", "false"}


def _guardrail_decision(payload: dict, capability: str, reason: str) -> AdmissionDecision:
    return AdmissionDecision(
        payload.get("entity_urn", ""),
        capability,
        False,
        reason,
        payload.get("context_contract", {}).get("verified_claims", []),
    )


def admit_capability(certificate: ReadinessCertificate | dict, capability: str) -> AdmissionDecision:
    """Make the final deterministic allow/block decision for an agent action."""
    payload = _payload(certificate)
    allowed = capability in payload["context_contract"]["allowed_capabilities"]
    matching = next((item for item in payload["certified_capabilities"] if item["capability"] == capability), None)
    if allowed:
        return AdmissionDecision(payload["entity_urn"], capability, True, "Capability is certified by the active policy.", payload["context_contract"].get("verified_claims", []))
    reason = "; ".join((matching or {}).get("reasons", [])) or "Capability is not certified by the active policy."
    return AdmissionDecision(payload["entity_urn"], capability, False, reason, payload["context_contract"].get("verified_claims", []))


def enforce_action_guardrails(
    certificate: ReadinessCertificate | dict,
    capability: str,
    base: AdmissionDecision | None = None,
) -> AdmissionDecision:
    """Apply action-specific controls after the policy decision.

    A healthy broad score is never enough to authorize destructive or
    restricted operations. These controls are deliberately conservative and
    deployment-independent; a deployment-specific adapter can relax them only
    after it proves permissions and scope.
    """
    payload = _payload(certificate)
    base = base or admit_capability(payload, capability)

    if capability == "modify-dataset":
        return _guardrail_decision(
            payload,
            capability,
            "Blocked by default: modifying a dataset requires explicit steward approval and a deployment-specific write adapter.",
        )

    if capability == "restricted-sql":
        return _guardrail_decision(
            payload,
            capability,
            "Blocked by default: restricted SQL requires an approved dataset and column scope that this deployment has not verified.",
        )

    if not base.allowed:
        return base

    if capability == "generate-executive-metrics":
        facts = _facts(payload)
        assertions = facts.get("assertions") or {}
        latest = _latest_assertions(facts)
        if not latest:
            return _guardrail_decision(
                payload,
                capability,
                "Blocked: the latest assertion result could not be verified for this asset.",
            )
        failed = next((item for item in latest if _assertion_failed(item)), None)
        if failed:
            name = failed.get("name") or failed.get("assertion_name") or "unnamed assertion"
            observed = failed.get("observed_at") or failed.get("timestamp") or "an unknown time"
            return _guardrail_decision(
                payload,
                capability,
                f"Blocked: latest assertion `{name}` failed at {observed}.",
            )
        freshness = facts.get("freshness") or {}
        timestamp = freshness.get("timestamp") or freshness.get("observed_at")
        if not timestamp or freshness.get("stale") is True:
            return _guardrail_decision(
                payload,
                capability,
                "Blocked: freshness timestamp or SLA status could not be verified for this asset.",
            )

    return base
