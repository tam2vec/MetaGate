#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
cd "$PROJECT_DIR"

printf '%s\n' '1/3 Running repository tests...'
PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-/tmp/predicate-pycache}" \
  PYTHONPATH=src python3 -m unittest discover -s tests -q

printf '%s\n' '2/3 Building the browser extension package...'
./scripts/package_extension.sh >/tmp/predicate-package.log
tail -n 1 /tmp/predicate-package.log

printf '%s\n' '3/3 Running the deterministic enforcement proof...'
PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-/tmp/predicate-pycache}" \
  PYTHONPATH=src python3 scripts/run_enforcement_demo.py \
    --datahub-file examples/data/six_asset_review_graph.json \
    >/tmp/predicate-enforcement-proof.json
PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-/tmp/predicate-pycache}" \
  python3 - <<'PY'
import json
from pathlib import Path

proof = json.loads(Path('/tmp/predicate-enforcement-proof.json').read_text())
decisions = {item['action']: item['decision'] for item in proof['decisions']}
expected = {
    'answer-business-questions': 'allowed',
    'generate-executive-metrics': 'blocked',
    'modify-dataset': 'blocked',
    'restricted-sql': 'blocked',
}
if decisions != expected:
    raise SystemExit(f'Unexpected enforcement proof: {decisions!r}')
if proof['integration_proof']['status'] != 'verified':
    raise SystemExit('Skill/MCP integration proof did not agree.')
print('Enforcement story, constraint contract, Skill, and MCP proof passed.')
PY

printf '%s\n' 'Optional live prerequisite status:'
if PYTHONPATH=src python3 -m predicate.doctor; then
  printf '%s\n' 'Local DataHub is reachable.'
else
  printf '%s\n' 'Local DataHub is not running; deterministic repository proof still passed.'
fi

printf '%s\n' 'Predicate verification passed.'
