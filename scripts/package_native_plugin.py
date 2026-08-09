#!/usr/bin/env python3
"""Build the deployment adapter bundle for a DataHub Action/webhook runner.

This is intentionally a small adapter bundle, not a pretend DataHub-core
plugin. The target deployment still supplies its registration and secrets.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/datahub-native-plugin"


def main() -> None:
    parser = argparse.ArgumentParser(description="Package MetaGate's DataHub preflight adapter")
    parser.add_argument(
        "--output",
        default=str(ROOT / "dist/metagate-datahub-preflight-adapter.zip"),
    )
    args = parser.parse_args()
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(path for path in SOURCE.rglob("*") if path.is_file())
    if not files:
        raise SystemExit(f"No adapter files found in {SOURCE}")
    with ZipFile(output, "w", ZIP_DEFLATED) as bundle:
        for path in files:
            bundle.write(path, path.relative_to(SOURCE).as_posix())
        bundle.writestr(
            "bundle.json",
            json.dumps(
                {
                    "name": "metagate-datahub-preflight-adapter",
                    "version": "1",
                    "kind": "deployment-adapter",
                    "entrypoint": "metagate.preflight",
                    "requires_deployment_registration": True,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
    print(f"Created {output}")
    print("The bundle includes handler.py, a deployment-neutral event bridge.")
    print("Register it through the target DataHub deployment's approved Action/webhook mechanism.")


if __name__ == "__main__":
    main()
