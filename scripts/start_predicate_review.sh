#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
cd "$PROJECT_DIR"

export DATAHUB_GRAPHQL_URL="${DATAHUB_GRAPHQL_URL:-http://localhost:8080/api/graphql}"

PYTHONPATH=src python3 scripts/serve_review.py \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --policy examples/policies/enterprise_ai.yml \
  --no-recorded-fallback \
  --urn "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)" \
  --urn "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_deleted,PROD)" \
  --urn "urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)" \
  --urn "urn:li:dataset:(urn:li:dataPlatform:kafka,SampleKafkaDataset,PROD)" \
  --urn "urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.customer_lifetime_value,PROD)"
