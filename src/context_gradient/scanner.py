from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Iterable, List

from context_gradient.datahub.adapter import DataHubEvidenceExtractor, DataHubWriteback
from context_gradient.sdk.diff import diff_certificates
from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.history import ReadinessHistory
from context_gradient.sdk.audit import AuditLog


@dataclass(frozen=True)
class ScanResult:
    urn: str
    certificate: dict
    diff: object
    duration_ms: float = 0.0


class BackgroundScanner:
    def __init__(
        self,
        extractor: DataHubEvidenceExtractor,
        engine: ReadinessEngine,
        history: ReadinessHistory,
        writeback: DataHubWriteback | None = None,
        audit_log: AuditLog | None = None,
    ):
        self.extractor = extractor
        self.engine = engine
        self.history = history
        self.writeback = writeback
        self.audit_log = audit_log

    def handle_metadata_events(self, urns: Iterable[str]) -> List[ScanResult]:
        results = []
        for urn in urns:
            started = perf_counter()
            self.extractor.invalidate(urn)
            bundle = self.extractor.bundle(urn)
            certificate = self.engine.certify(bundle)
            previous = self.history.latest_certificate(urn)
            diff = diff_certificates(previous, certificate)
            self.history.append(certificate)
            payload = certificate.as_dict()
            if self.writeback:
                self.writeback.publish(urn, payload)
            if self.audit_log:
                self.audit_log.append("certification", urn, payload)
            results.append(ScanResult(urn, payload, diff, round((perf_counter() - started) * 1000, 2)))
        return results

    def handle_events(self, events: Iterable[dict]) -> List[ScanResult]:
        """Process DataHub metadata-change events, deduplicating entity URNs."""
        urns = list(dict.fromkeys(event["entityUrn"] for event in events if event.get("entityUrn")))
        return self.handle_metadata_events(urns)
