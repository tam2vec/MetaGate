#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
OUTPUT=${PREDICATE_RELEASE_PROOF_OUTPUT:-/tmp/predicate-release-proof.json}
cd "$PROJECT_DIR"

printf '%s\n' 'Predicate judge proof'
printf '%s\n' '---------------------'
PYTHONPATH=src python3 scripts/build_release_proof.py --output "$OUTPUT"
printf '\n%s\n' 'Open the local demo: http://127.0.0.1:8765/review'
printf '%s\n' "Proof JSON: $OUTPUT"
printf '%s\n' 'For live DataHub evidence, set DATAHUB_GRAPHQL_URL and PREDICATE_LIVE_DATAHUB_URN before rerunning.'
