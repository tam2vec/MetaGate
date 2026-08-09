#!/usr/bin/env bash
set -euo pipefail

DATAHUB_BIN="${DATAHUB_BIN:-datahub}"

echo "Loading hackathon datapacks into the running local DataHub..."
"$DATAHUB_BIN" docker check
"$DATAHUB_BIN" datapack load showcase-ecommerce --force
"$DATAHUB_BIN" datapack load bootstrap --force

cat <<'EOF'
Loaded CLI datapacks: showcase-ecommerce and bootstrap.
The nyc-taxi, healthcare, and fiction-retail resources are published scenario
datasets, not CLI datapack names in every DataHub CLI release. Load them with
their published recipes, then let MetaGate discovery add their resulting
dataset URNs after indexing. MetaGate never invents URNs for an unloaded
resource.
EOF
