from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from context_gradient.sdk.models import ReadinessCertificate


class ReadinessHistory:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def latest(self, entity_urn: str) -> Optional[dict]:
        files = sorted(self.directory.glob(self._prefix(entity_urn) + "*.json"))
        if not files:
            return None
        return json.loads(files[-1].read_text())

    def latest_certificate(self, entity_urn: str) -> Optional[dict]:
        return self.latest(entity_urn)

    def append(self, certificate: ReadinessCertificate) -> Path:
        stamp = certificate.issued_at.strftime("%Y%m%d%H%M%S")
        path = self.directory / f"{self._prefix(certificate.entity_urn)}{stamp}.json"
        path.write_text(json.dumps(certificate.as_dict(), indent=2, sort_keys=True) + "\n")
        return path

    def _prefix(self, entity_urn: str) -> str:
        safe = "".join(ch if ch.isalnum() else "_" for ch in entity_urn)
        return safe + "__"
