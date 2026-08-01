from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


class AuditLog:
    """Append-only local audit log for certification and admission decisions."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, action: str, entity_urn: str, result: Dict[str, Any]) -> None:
        record = {"timestamp": datetime.now(timezone.utc).isoformat(), "action": action, "entity_urn": entity_urn, "result": result}
        with self.path.open("a") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
