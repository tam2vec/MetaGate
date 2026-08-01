from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Mapping

try:
    import yaml
except ImportError:  # pragma: no cover - exercised when PyYAML is unavailable.
    yaml = None

from context_gradient.sdk.models import EvidenceKind


@dataclass(frozen=True)
class CapabilityPolicy:
    name: str
    minimum_score: float
    minimum_confidence: float
    required_evidence: List[EvidenceKind]


@dataclass(frozen=True)
class PolicyProfile:
    name: str
    evidence_weights: Dict[EvidenceKind, float]
    stale_after_days: Dict[EvidenceKind, int]
    capability_policies: List[CapabilityPolicy]
    minimum_score: float = 80.0
    graph_propagation: float = 0.15


DEFAULT_EVIDENCE_WEIGHTS = {
    EvidenceKind.DESCRIPTION: 0.8,
    EvidenceKind.OWNERSHIP: 1.0,
    EvidenceKind.GLOSSARY: 0.9,
    EvidenceKind.DOMAIN: 0.8,
    EvidenceKind.TAGS: 0.6,
    EvidenceKind.LINEAGE: 1.0,
    EvidenceKind.COLUMN_LINEAGE: 1.1,
    EvidenceKind.ASSERTIONS: 1.2,
    EvidenceKind.INCIDENTS: 1.1,
    EvidenceKind.FRESHNESS: 1.0,
    EvidenceKind.USAGE: 0.7,
    EvidenceKind.DASHBOARDS: 0.8,
    EvidenceKind.CHARTS: 0.6,
    EvidenceKind.ML_MODELS: 0.8,
    EvidenceKind.DOWNSTREAM_CONSUMERS: 1.0,
    EvidenceKind.POLICY: 1.2,
}


def _kind_map(raw: Mapping[str, float]) -> Dict[EvidenceKind, float]:
    result = dict(DEFAULT_EVIDENCE_WEIGHTS)
    for key, value in raw.items():
        result[EvidenceKind(key)] = float(value)
    return result


def load_policy(path: str | Path) -> PolicyProfile:
    text = Path(path).read_text()
    data = yaml.safe_load(text) if yaml else _minimal_yaml(text)
    data = data or {}
    capability_policies = [
        CapabilityPolicy(
            name=item["name"],
            minimum_score=float(item.get("minimum_score", data.get("minimum_score", 80))),
            minimum_confidence=float(item.get("minimum_confidence", 70)),
            required_evidence=[EvidenceKind(kind) for kind in item.get("required_evidence", [])],
        )
        for item in data.get("capabilities", [])
    ]
    return PolicyProfile(
        name=data.get("name", "default"),
        evidence_weights=_kind_map(data.get("evidence_weights", {})),
        stale_after_days={
            EvidenceKind(kind): int(days) for kind, days in data.get("stale_after_days", {}).items()
        },
        capability_policies=capability_policies,
        minimum_score=float(data.get("minimum_score", 80)),
        graph_propagation=float(data.get("graph_propagation", 0.15)),
    )


def _minimal_yaml(text: str) -> dict:
    """Parse the simple policy YAML shape used by bundled examples."""
    result: dict = {}
    section = None
    current_item = None
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.strip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if indent == 0 and line.endswith(":"):
            section = line[:-1]
            result[section] = [] if section == "capabilities" else {}
            current_item = None
        elif indent == 0:
            key, value = line.split(":", 1)
            result[key] = _parse_scalar(value.strip())
            section = None
        elif section == "capabilities" and line.startswith("- "):
            key, value = line[2:].split(":", 1)
            current_item = {key: _parse_scalar(value.strip())}
            result[section].append(current_item)
        elif section == "capabilities" and current_item is not None:
            key, value = line.split(":", 1)
            current_item[key] = _parse_scalar(value.strip())
        elif section:
            key, value = line.split(":", 1)
            result[section][key] = _parse_scalar(value.strip())
    return result


def _parse_scalar(value: str):
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        return [item.strip() for item in inner.split(",")] if inner else []
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value
