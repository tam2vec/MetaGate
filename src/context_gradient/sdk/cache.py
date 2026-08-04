from __future__ import annotations

import json
import time
from threading import RLock
from pathlib import Path
from typing import Any, Optional


class JsonCache:
    def __init__(self, path: str | Path, ttl_seconds: int = 300):
        self.path = Path(path)
        self.ttl_seconds = ttl_seconds
        self._lock = RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}")

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            data = json.loads(self.path.read_text())
            entry = data.get(key)
            if not entry:
                return None
            if time.time() - entry["created_at"] > self.ttl_seconds:
                return None
            return entry["value"]

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            data = json.loads(self.path.read_text())
            data[key] = {"created_at": time.time(), "value": value}
            self.path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

    def delete(self, key: str) -> None:
        with self._lock:
            data = json.loads(self.path.read_text())
            if key in data:
                del data[key]
                self.path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
