#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
cd "$PROJECT_DIR"

export DATAHUB_GRAPHQL_URL="${DATAHUB_GRAPHQL_URL:-http://localhost:8080/api/graphql}"
export METAGATE_PORT="${METAGATE_PORT:-8765}"
export METAGATE_MAX_ASSETS="${METAGATE_MAX_ASSETS:-0}"
# Live mode is catalog-first: every dataset returned by the connected DataHub
# is evaluated. The six proof assets are retained only for fixture/demo mode.
export METAGATE_DISCOVER_ASSETS="${METAGATE_DISCOVER_ASSETS:-1}"
export METAGATE_CATALOG_FIRST="${METAGATE_CATALOG_FIRST:-1}"
export METAGATE_LOAD_HACKATHON_DATAPACKS="${METAGATE_LOAD_HACKATHON_DATAPACKS:-0}"
export METAGATE_AGENT_REGISTRY_FILE="${METAGATE_AGENT_REGISTRY_FILE:-$PROJECT_DIR/examples/data/agent_registry.json}"
export METAGATE_AGENT_ID="${METAGATE_AGENT_ID:-urn:li:aiAgent:metagate-review-agent}"
export METAGATE_SKILL_ID="${METAGATE_SKILL_ID:-urn:li:agentSkill:metagate-preflight}"
export METAGATE_TOOL_ID="${METAGATE_TOOL_ID:-urn:li:api:metagate.evaluate}"
export METAGATE_SERVICE_ID="${METAGATE_SERVICE_ID:-urn:li:service:metagate-review-api}"
export METAGATE_REQUIRE_AGENT_REGISTRY="${METAGATE_REQUIRE_AGENT_REGISTRY:-1}"
export METAGATE_RUNTIME_ROOT="${METAGATE_RUNTIME_ROOT:-$PROJECT_DIR}"
if [ -z "${METAGATE_BUILD_ID:-}" ]; then
  if git rev-parse --short HEAD >/dev/null 2>&1; then
    METAGATE_BUILD_ID="source-$(git rev-parse --short HEAD)"
  else
    METAGATE_BUILD_ID="source-local"
  fi
  export METAGATE_BUILD_ID
fi

# Stop a MetaGate runtime owned by launchd and, if necessary, its listener.
# This keeps a login-started copy from silently winning over the project the
# user just opened in Terminal.
stop_existing_metagate() {
  launchctl bootout "gui/$(id -u)/com.metagate.review" 2>/dev/null || true
  if command -v lsof >/dev/null 2>&1; then
    old_pid="$(lsof -tiTCP:${METAGATE_PORT} -sTCP:LISTEN 2>/dev/null | head -n 1 || true)"
    if [ -n "$old_pid" ]; then
      kill "$old_pid" 2>/dev/null || true
      for _ in 1 2 3 4 5; do
        if ! kill -0 "$old_pid" 2>/dev/null; then break; fi
        sleep 1
      done
    fi
  fi
}

# Always replace a stale launch-agent runtime. A healthy process from this
# project is reused unless METAGATE_FORCE_RESTART is set; a process from
# ~/MetaGateRuntime or another checkout is stopped so the URL cannot serve a
# different build than the current folder.
force_restart=0
case "${METAGATE_FORCE_RESTART:-0}" in
  1|true|yes) force_restart=1 ;;
esac

if running_status="$(curl -fsS --max-time 1 "http://127.0.0.1:${METAGATE_PORT}/api/status" 2>/dev/null)"; then
  running_root="$(printf '%s' "$running_status" | python3 -c 'import json,sys; print((json.load(sys.stdin).get("runtime") or {}).get("runtime_root", ""))' 2>/dev/null || true)"
  if [ "$running_root" = "$PROJECT_DIR" ] && [ "$force_restart" -eq 0 ]; then
    echo "MetaGate is already running from the current project at http://127.0.0.1:${METAGATE_PORT}/review"
    exit 0
  fi
  if [ "$running_root" = "$PROJECT_DIR" ]; then
    echo "Restarting MetaGate from the current project"
  else
    echo "Replacing stale MetaGate runtime: ${running_root:-unknown}"
  fi
  stop_existing_metagate
elif [ "$force_restart" -eq 1 ]; then
  stop_existing_metagate
fi

if [ "$METAGATE_LOAD_HACKATHON_DATAPACKS" = "1" ]; then
  "$PROJECT_DIR/scripts/load_hackathon_datapacks.sh"
fi

if command -v lsof >/dev/null 2>&1; then
  occupied_pid="$(lsof -tiTCP:${METAGATE_PORT} -sTCP:LISTEN 2>/dev/null | head -n 1 || true)"
  if [ -n "$occupied_pid" ]; then
    echo "Port ${METAGATE_PORT} is already used by process ${occupied_pid}." >&2
    echo "Stop that process, or run with METAGATE_PORT=8766." >&2
    exit 1
  fi
fi

set -- scripts/serve_review.py \
  --datahub-url "$DATAHUB_GRAPHQL_URL" \
  --port "$METAGATE_PORT" \
  --policy examples/policies/enterprise_ai.yml \
  --no-recorded-fallback \
  --registry-file "$METAGATE_AGENT_REGISTRY_FILE" \
  --agent-id "$METAGATE_AGENT_ID" \
  --skill-id "$METAGATE_SKILL_ID" \
  --tool-id "$METAGATE_TOOL_ID" \
  --service-id "$METAGATE_SERVICE_ID"

if [ "$METAGATE_REQUIRE_AGENT_REGISTRY" = "1" ] || [ "$METAGATE_REQUIRE_AGENT_REGISTRY" = "true" ] || [ "$METAGATE_REQUIRE_AGENT_REGISTRY" = "yes" ]; then
  set -- "$@" --require-agent-registry
fi

catalog_first_enabled=0
case "$METAGATE_CATALOG_FIRST" in
  1|true|yes) catalog_first_enabled=1 ;;
esac

if [ "$catalog_first_enabled" -eq 0 ]; then
  for urn in \
    "urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)" \
    "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)" \
    "urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_deleted,PROD)" \
    "urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)" \
    "urn:li:dataset:(urn:li:dataPlatform:kafka,SampleKafkaDataset,PROD)" \
    "urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.customer_lifetime_value,PROD)"
  do
    set -- "$@" --urn "$urn"
  done
fi

if [ "${METAGATE_DISCOVER_ASSETS:-0}" = "1" ] || [ "$catalog_first_enabled" -eq 1 ]; then
  set -- "$@" --discover-assets --max-assets "$METAGATE_MAX_ASSETS"
fi
if [ "$catalog_first_enabled" -eq 1 ]; then
  set -- "$@" --catalog-first
fi

PYTHONPATH=src python3 "$@"
