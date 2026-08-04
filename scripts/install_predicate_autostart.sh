#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
# launchd may be denied access to a project inside Documents. Keep a clean,
# user-owned runtime copy outside protected folders and use absolute paths.
RUNTIME_DIR="$HOME/PredicateRuntime"
PYTHON_BIN=${PYTHON_BIN:-$(command -v python3)}
LABEL="com.predicate.review"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs/Predicate"

mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"
# Stop the previous service and replace only the generated runtime copy.
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -rf "$RUNTIME_DIR"
mkdir -p "$RUNTIME_DIR"
for runtime_item in src scripts public-demo examples pyproject.toml; do
  if [ -e "$PROJECT_DIR/$runtime_item" ]; then
    cp -R "$PROJECT_DIR/$runtime_item" "$RUNTIME_DIR/"
  fi
done

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
    <string>--urn</string>
    <string>urn:li:dataset:(urn:li:dataPlatform:snowflake,analytics.revenue_daily,PROD)</string>
    <string>--urn</string>
    <string>urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_created,PROD)</string>
    <string>--urn</string>
    <string>urn:li:dataset:(urn:li:dataPlatform:hive,fct_users_deleted,PROD)</string>
    <string>--urn</string>
    <string>urn:li:dataset:(urn:li:dataPlatform:hive,SampleHiveDataset,PROD)</string>
    <string>--urn</string>
    <string>urn:li:dataset:(urn:li:dataPlatform:kafka,SampleKafkaDataset,PROD)</string>
    <string>--urn</string>
    <string>urn:li:dataset:(urn:li:dataPlatform:snowflake,finance.customer_lifetime_value,PROD)</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$RUNTIME_DIR</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONPATH</key>
    <string>$RUNTIME_DIR/src</string>
    <key>DATAHUB_GRAPHQL_URL</key>
    <string>http://localhost:8080/api/graphql</string>
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
  printf 'Predicate could not start. Check %s/review.error.log.\n' "$LOG_DIR" >&2
  exit 1
fi

printf 'Predicate is running and starts automatically at login.\n'
printf 'Review page: http://127.0.0.1:8765/review\n'
printf 'Logs: %s/review.log and %s/review.error.log\n' "$LOG_DIR" "$LOG_DIR"
