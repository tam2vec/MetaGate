"""Build a machine-readable, honest release proof for MetaGate.

The proof separates deterministic repository checks from checks that require a
running DataHub, credentials, reviewers, or a deployment. It is safe to run
in CI or before a hackathon demo and does not send data to a remote service by
itself.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
ENV = {**os.environ, "PYTHONPATH": "src:."}
ENV.setdefault("PYTHONPYCACHEPREFIX", "/tmp/metagate-release-pycache")


def run(command: list[str], *, timeout: int = 180) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=ENV,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        return {
            "command": " ".join(command),
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "ok": completed.returncode == 0,
        }
    except Exception as error:
        return {
            "command": " ".join(command),
            "returncode": None,
            "stdout": "",
            "stderr": str(error),
            "ok": False,
        }


def parse_json_output(result: dict[str, Any]) -> dict[str, Any] | None:
    try:
        return json.loads(result["stdout"])
    except (KeyError, TypeError, json.JSONDecodeError):
        return None


def test_summary(output: str) -> dict[str, Any]:
    match = re.search(r"Ran (\d+) tests? in ([0-9.]+)s", output)
    skipped = re.search(r"skipped=(\d+)", output)
    return {
        "tests": int(match.group(1)) if match else None,
        "seconds": float(match.group(2)) if match else None,
        "skipped": int(skipped.group(1)) if skipped else 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build MetaGate's release proof bundle")
    parser.add_argument(
        "--output",
        default="/tmp/metagate-release-proof.json",
        help="Where to write the JSON proof (default: /tmp/metagate-release-proof.json)",
    )
    args = parser.parse_args()

    tests = run([PYTHON, "-m", "unittest", "discover", "-s", "tests", "-q"])
    benchmark = run([PYTHON, "scripts/evaluate_benchmark.py"])
    enforcement = run(
        [
            PYTHON,
            "scripts/run_enforcement_demo.py",
            "--datahub-file",
            "examples/data/six_asset_review_graph.json",
        ]
    )
    package = run(["sh", "scripts/package_extension.sh"])
    native_package = run(
        [
            PYTHON,
            "scripts/package_native_plugin.py",
            "--output",
            "/tmp/metagate-datahub-preflight-adapter.zip",
        ]
    )
    adversarial = run([PYTHON, "scripts/generate_adversarial_scenarios.py", "--json"])
    doctor = run([PYTHON, "-m", "metagate.doctor"])
    doctor_payload = parse_json_output(doctor)

    # Configuration alone is not proof. When an official DataHub MCP command
    # is supplied, run the real probe and preserve its response in the proof
    # bundle so a judge can distinguish configured from verified.
    if os.environ.get("METAGATE_DATAHUB_MCP_COMMAND", "").strip():
        official_mcp = run([PYTHON, "scripts/probe_datahub_mcp.py"], timeout=120)
        official_mcp_payload = parse_json_output(official_mcp)
    else:
        official_mcp = None
        official_mcp_payload = None

    if os.environ.get("DATAHUB_GRAPHQL_URL") and os.environ.get("METAGATE_LIVE_DATAHUB_URN"):
        live_schema_run = run(
            [PYTHON, "-m", "unittest", "tests.test_datahub_schema", "-q"],
            timeout=240,
        )
        live_schema: dict[str, Any] = {
            "status": "verified" if live_schema_run["ok"] else "failed",
            "run": live_schema_run,
        }
    else:
        live_schema = {
            "status": "not_configured",
            "note": "Set DATAHUB_GRAPHQL_URL and METAGATE_LIVE_DATAHUB_URN to run against a real deployment.",
        }

    enforcement_payload = parse_json_output(enforcement) or {}
    decisions = {
        item.get("action"): item.get("decision")
        for item in enforcement_payload.get("decisions", [])
        if isinstance(item, dict)
    }
    required = {
        "tests": tests["ok"],
        "benchmark": benchmark["ok"],
        "enforcement_story": (
            enforcement["ok"]
            and enforcement_payload.get("integration_proof", {}).get("status") == "verified"
        ),
        "extension_package": package["ok"],
        "native_adapter_package": native_package["ok"],
        "adversarial_scenarios": adversarial["ok"],
    }
    proof = {
        "product": "MetaGate",
        "proof_version": "1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": {
            "branch": run(["git", "branch", "--show-current"])["stdout"].strip(),
            "commit": run(["git", "rev-parse", "HEAD"])["stdout"].strip(),
        },
        "required_checks": required,
        "status": "ready_for_review" if all(required.values()) else "attention_required",
        "deterministic_proof": {
            "tests": {
                "status": "verified" if tests["ok"] else "failed",
                **test_summary(tests["stdout"] + tests["stderr"]),
            },
            "curated_benchmark": {"status": "verified" if benchmark["ok"] else "failed"},
            "enforcement_story": {
                "status": "verified" if required["enforcement_story"] else "failed",
                "decisions": decisions,
                "integration_proof": enforcement_payload.get("integration_proof", {}),
            },
            "browser_extension": {
                "status": "verified" if package["ok"] else "failed",
                "artifact": "dist/MetaGate-DataHub-extension.zip",
            },
            "native_datahub_adapter": {
                "status": "packaged" if native_package["ok"] else "failed",
                "artifact": "/tmp/metagate-datahub-preflight-adapter.zip",
                "registration": "deployment-specific",
            },
            "adversarial_scenarios": {
                "status": "generated" if adversarial["ok"] else "failed",
                "count": (parse_json_output(adversarial) or {}).get("count", 0),
                "labels": "synthetic_only",
            },
        },
        "deployment_checks": {
            "local_prerequisites": {
                "status": "verified" if doctor_payload and doctor_payload.get("required_ready") else "unavailable",
                "checks": doctor_payload.get("checks", []) if doctor_payload else [],
                "summary": doctor_payload.get("summary") if doctor_payload else doctor["stderr"].strip(),
            },
            "live_schema_contract": live_schema,
        },
        "external_proof_required": {
            "official_datahub_mcp": (
                "verified"
                if official_mcp_payload and official_mcp_payload.get("status") == "verified"
                else (
                    "configured_but_unverified"
                    if official_mcp
                    else "not_configured"
                )
            ),
            "live_writeback": "Run the approved deployment-specific mutation with an authorized token, then verify the contract in DataHub.",
            "independent_labels": "Have independent reviewers label the held-out cases; do not manufacture labels.",
            "native_plugin": "Install the packaged browser integration or deployment-specific DataHub extension and capture it on a real asset page.",
            "public_live_datahub": "Use a reachable, permissioned DataHub service; localhost cannot be a public deployment dependency.",
        },
    }
    proof["external_proof_observations"] = {
        "official_datahub_mcp": official_mcp_payload or {
            "status": "not_configured",
            "note": "Set METAGATE_DATAHUB_MCP_COMMAND to run the official probe.",
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": proof["status"],
        "output": str(output),
        "commit": proof["repository"]["commit"],
        "required_checks": required,
        "live_schema": live_schema["status"],
    }, indent=2))
    if proof["status"] != "ready_for_review":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
