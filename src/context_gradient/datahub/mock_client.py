from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable


class FileDataHubClient:
    """Local stand-in for DataHub GraphQL/OpenAPI calls used by tests and demos."""

    def __init__(self, path: str | Path, output_path: str | Path | None = None):
        self.path = Path(path)
        self.output_path = Path(output_path) if output_path else self.path.parent / "writeback.json"
        self.data = json.loads(self.path.read_text())

    def get_entity(self, urn: str) -> Dict[str, Any]:
        self.data = json.loads(self.path.read_text())
        return self.data["entities"][urn]

    def list_dataset_urns(self) -> list[str]:
        self.data = json.loads(self.path.read_text())
        return sorted(
            urn for urn, entity in self.data.get("entities", {}).items()
            if entity.get("type", "dataset").lower() == "dataset"
        )

    def get_neighbors(self, urn: str) -> Iterable[Dict[str, Any]]:
        entity = self.get_entity(urn)
        neighbor_urns = set(entity.get("upstreams", []) + entity.get("downstreams", []))
        return [self.data["entities"][neighbor] for neighbor in neighbor_urns if neighbor in self.data["entities"]]

    def write_certificate(self, urn: str, certificate: Dict[str, Any]) -> None:
        payload = self._read_output()
        payload.setdefault("certificates", {})[urn] = certificate
        self._write_output(payload)

    def create_remediation_task(self, urn: str, title: str, body: str) -> None:
        payload = self._read_output()
        task = {"urn": urn, "title": title, "body": body}
        tasks = payload.setdefault("tasks", [])
        if task not in tasks:
            tasks.append(task)
        self._write_output(payload)

    def _read_output(self) -> Dict[str, Any]:
        if self.output_path.exists():
            return json.loads(self.output_path.read_text())
        return {}

    def _write_output(self, payload: Dict[str, Any]) -> None:
        self.output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

    def get_written_certificate(self, urn: str) -> Dict[str, Any] | None:
        return self._read_output().get("certificates", {}).get(urn)
