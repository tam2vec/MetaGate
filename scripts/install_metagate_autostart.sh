#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
# The project checkout remains authoritative, but macOS launchd can deny
# background services access to Documents. Syncing a runtime copy avoids that
# privacy trap while the runtime identity still reports the source checkout.
# Set METAGATE_AUTOSTART_MODE=source only when Documents access is explicitly
# available and a source checkout runtime is desired.
AUTOSTART_MODE="${METAGATE_AUTOSTART_MODE:-copy}"
RUNTIME_DIR="$PROJECT_DIR"
if [ "$AUTOSTART_MODE" = "copy" ]; then
  RUNTIME_DIR="$HOME/MetaGateRuntime"
fi
PYTHON_BIN=${PYTHON_BIN:-$(command -v python3)}
LABEL="com.metagate.review"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs/MetaGate"

export METAGATE_RUNTIME_ROOT="$RUNTIME_DIR"
if [ -z "${METAGATE_BUILD_ID:-}" ]; then
  if git -C "$PROJECT_DIR" rev-parse --short HEAD >/dev/null 2>&1; then
    METAGATE_BUILD_ID="source-$(git -C "$PROJECT_DIR" rev-parse --short HEAD)"
    if [ -n "$(git -C "$PROJECT_DIR" status --porcelain)" ]; then
      METAGATE_BUILD_ID="$METAGATE_BUILD_ID-dirty"
    fi
  else
    METAGATE_BUILD_ID="source-local"
  fi
  export METAGATE_BUILD_ID
fi

mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"
# Stop the previous service before replacing its launch configuration.
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true

# launchd may have left an older manual or copied runtime holding the review
# port. Stop that listener before replacing files so this installation cannot
# silently serve a stale build or enter a restart loop.
stop_port_listener() {
  if ! command -v lsof >/dev/null 2>&1; then
    return 0
  fi

  old_pid="$(lsof -tiTCP:8765 -sTCP:LISTEN 2>/dev/null | head -n 1 || true)"
  if [ -z "$old_pid" ]; then
    return 0
  fi

  kill "$old_pid" 2>/dev/null || true
  for _ in 1 2 3 4 5; do
    if ! kill -0 "$old_pid" 2>/dev/null; then
      return 0
    fi
    sleep 1
  done

  printf 'Port 8765 is still held by process %s; MetaGate was not replaced.\n' "$old_pid" >&2
  return 1
}

stop_port_listener
if [ "$AUTOSTART_MODE" = "copy" ]; then
  rm -rf "$RUNTIME_DIR"
  mkdir -p "$RUNTIME_DIR"
  for runtime_item in src scripts public-demo examples pyproject.toml; do
    if [ -e "$PROJECT_DIR/$runtime_item" ]; then
      cp -R "$PROJECT_DIR/$runtime_item" "$RUNTIME_DIR/"
    fi
  done
fi

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON_BIN</string>
    <string>$RUNTIME_DIR/scripts/serve_review.py</string>
    <string>--host</string>
    <string>127.0.0.1</string>
    <string>--port</string>
    <string>8765</string>
    <string>--datahub-url</string>
    <string>http://localhost:8080/api/graphql</string>
    <string>--policy</string>
    <string>$RUNTIME_DIR/examples/policies/enterprise_ai.yml</string>
    <string>--no-recorded-fallback</string>
    <string>--registry-file</string>
    <string>$RUNTIME_DIR/examples/data/agent_registry.json</string>
    <string>--agent-id</string>
    <string>urn:li:aiAgent:metagate-review-agent</string>
    <string>--skill-id</string>
    <string>urn:li:agentSkill:metagate-preflight</string>
    <string>--tool-id</string>
    <string>urn:li:api:metagate.evaluate</string>
    <string>--service-id</string>
    <string>urn:li:service:metagate-review-api</string>
    <string>--require-agent-registry</string>
    <string>--discover-assets</string>
    <string>--catalog-first</string>
    <string>--max-assets</string>
    <string>${METAGATE_MAX_ASSETS:-0}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$RUNTIME_DIR</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin</string>
    <key>PYTHONPATH</key>
    <string>$RUNTIME_DIR/src</string>
    <key>DATAHUB_GRAPHQL_URL</key>
    <string>${DATAHUB_GRAPHQL_URL:-http://localhost:8080/api/graphql}</string>
    <key>DATAHUB_GMS_URL</key>
    <string>${DATAHUB_GMS_URL:-http://localhost:8080}</string>
    <key>DATAHUB_GMS_TOKEN</key>
    <string>${DATAHUB_GMS_TOKEN:-}</string>
    <key>METAGATE_DATAHUB_MCP_COMMAND</key>
    <string>${METAGATE_DATAHUB_MCP_COMMAND:-}</string>
    <key>METAGATE_BUILD_ID</key>
    <string>$METAGATE_BUILD_ID</string>
    <key>METAGATE_RUNTIME_ROOT</key>
    <string>$RUNTIME_DIR</string>
    <key>METAGATE_SOURCE_ROOT</key>
    <string>$PROJECT_DIR</string>
    <key>METAGATE_WRITEBACK_RECEIPT</key>
    <string>$HOME/.metagate/writeback-receipt.json</string>
    <key>METAGATE_AGENT_REGISTRY_FILE</key>
    <string>$RUNTIME_DIR/examples/data/agent_registry.json</string>
    <key>METAGATE_AGENT_ID</key>
    <string>urn:li:aiAgent:metagate-review-agent</string>
    <key>METAGATE_SKILL_ID</key>
    <string>urn:li:agentSkill:metagate-preflight</string>
    <key>METAGATE_TOOL_ID</key>
    <string>urn:li:api:metagate.evaluate</string>
    <key>METAGATE_SERVICE_ID</key>
    <string>urn:li:service:metagate-review-api</string>
    <key>METAGATE_REQUIRE_AGENT_REGISTRY</key>
    <string>1</string>
    <key>METAGATE_DISCOVER_ASSETS</key>
    <string>1</string>
    <key>METAGATE_CATALOG_FIRST</key>
    <string>1</string>
    <key>METAGATE_MAX_ASSETS</key>
    <string>${METAGATE_MAX_ASSETS:-0}</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>5</integer>
  <key>StandardOutPath</key>
  <string>$LOG_DIR/review.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/review.error.log</string>
</dict>
</plist>
EOF

launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl enable "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl kickstart -k "gui/$(id -u)/$LABEL" 2>/dev/null || true

# Do not claim success until the actual review process is listening.
ready=0
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS http://127.0.0.1:8765/healthz >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done

if [ "$ready" -ne 1 ]; then
  if [ "$AUTOSTART_MODE" = "source" ]; then
    printf 'macOS blocked launchd from reading the Documents checkout; syncing the current checkout once into ~/MetaGateRuntime so the service can run.\n' >&2
    exec env METAGATE_AUTOSTART_MODE=copy "$0"
  fi
  printf 'MetaGate could not start. Check %s/review.error.log.\n' "$LOG_DIR" >&2
  exit 1
fi

printf 'MetaGate is running and starts automatically at login.\n'
printf 'Review page: http://127.0.0.1:8765/review\n'
printf 'Logs: %s/review.log and %s/review.error.log\n' "$LOG_DIR" "$LOG_DIR"
