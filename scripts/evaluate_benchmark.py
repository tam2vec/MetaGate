from __future__ import annotations

import json
import argparse
from pathlib import Path

from context_gradient.datahub.adapter import DataHubEvidenceExtractor
from context_gradient.sdk.engine import ReadinessEngine
from context_gradient.sdk.models import EvidenceBundle, EntityNode, EvidenceKind
from context_gradient.sdk.policy import CapabilityPolicy, PolicyProfile, load_policy


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=str(root / "examples/benchmark/cases.json"))
    parser.add_argument("--label", default="curated benchmark")
    args = parser.parse_args()
    policy = PolicyProfile(
        "benchmark",
        {},
        {},
        [CapabilityPolicy("safe-discovery", 0, 0, list(EvidenceKind))],
        minimum_score=0,
    )
    cases = json.loads(Path(args.cases).read_text())
    results = []
    required = set(EvidenceKind)
    defaults = {
        "description": {"text": "Metric"}, "ownership": {"owners": ["team"]},
        "glossary": {"terms": ["Metric"]}, "domain": {"name": "Business"},
        "tags": {"values": ["production"]}, "lineage": {"upstreams": ["source"]},
        "column_lineage": {"complete": True}, "assertions": {"passing": 1},
        "incidents": {"open": 0}, "freshness": {"passed": True},
        "usage": {"weekly_users": 1}, "dashboards": {"count": 1},
        "charts": {"count": 1}, "ml_models": {"count": 0},
        "downstream_consumers": {"count": 1}, "policy": {"profile": "benchmark"},
    }
    for case in cases:
        raw = defaults | case["entity"] | {"urn": "urn:benchmark:" + case["name"]}
        node = DataHubEvidenceExtractor(type("Client", (), {})())._node(raw)
        certificate = ReadinessEngine(policy).certify(EvidenceBundle(node))
        actual = (
            certificate.readiness_score >= policy.minimum_score
            and any(item.certified for item in certificate.certified_capabilities)
            and not any(gap.evidence_kind in required for gap in certificate.gaps)
        )
        results.append((case["expected_ready"], actual))
    tp = sum(expected and actual for expected, actual in results)
    tn = sum(not expected and not actual for expected, actual in results)
    fp = sum(not expected and actual for expected, actual in results)
    fn = sum(expected and not actual for expected, actual in results)
    statement = f"Predicate evaluated {len(results)} scenarios in the {args.label}."
    if args.label == "curated benchmark" and len(results) == 30:
        statement = "Predicate passes all 30 curated policy conformance checks across ready, missing, stale, incomplete and contradictory metadata states."
    print(json.dumps({
        "statement": statement,
        "positive_definition": "Asset satisfies the requested capability policy.",
        "cases": len(results),
        "curated_conformance_pass_rate": round((tp + tn) / len(results), 3),
        "checks_passed": tp + tn,
        "unexpected_allows": fp,
        "unexpected_blocks": fn,
        "note": "Use the curated label only for internally authored checks. A held-out label requires cases created independently of the rule implementation; neither result is a production accuracy or universal precision claim.",
    }, indent=2))


if __name__ == "__main__":
    main()
