#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
cd "$PROJECT_DIR"

export PREDICATE_DEMO_MODE=fixture
export PREDICATE_PORT="${PREDICATE_PORT:-8765}"

printf '%s\n' 'Predicate six-asset demo is starting.'
printf '%s\n' "Review page: http://127.0.0.1:${PREDICATE_PORT}/review"
printf '%s\n' 'Source: examples/data/six_asset_review_graph.json'
printf '%s\n' 'This is a deterministic fixture demo. Use start_predicate_review.sh for live DataHub.'

PYTHONPATH=src python3 scripts/serve_review.py \
  --host 127.0.0.1 \
  --port "$PREDICATE_PORT" \
  --policy examples/policies/enterprise_ai.yml \
  --datahub-file examples/data/six_asset_review_graph.json \
  --no-recorded-fallback
