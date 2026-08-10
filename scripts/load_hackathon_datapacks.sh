#!/usr/bin/env bash
set -euo pipefail

DATAHUB_BIN="${DATAHUB_BIN:-datahub}"
DATAHUB_PYTHON="${DATAHUB_PYTHON:-python3}"
STATIC_ASSETS_DIR="${STATIC_ASSETS_DIR:-${TMPDIR:-/tmp}/metagate-datahub-static-assets}"
STATIC_ASSETS_REPO="https://github.com/datahub-project/static-assets.git"

echo "Loading hackathon datapacks into the running local DataHub..."
"$DATAHUB_BIN" docker check
"$DATAHUB_BIN" datapack load showcase-ecommerce --force
"$DATAHUB_BIN" datapack load bootstrap --force

if [[ ! -d "$STATIC_ASSETS_DIR/.git" ]]; then
  echo "Downloading the official DataHub static-assets recipes..."
  mkdir -p "$(dirname "$STATIC_ASSETS_DIR")"
  git clone --filter=blob:none --sparse "$STATIC_ASSETS_REPO" "$STATIC_ASSETS_DIR"
  (
    cd "$STATIC_ASSETS_DIR"
    git sparse-checkout set datasets/nyc-taxi datasets/healthcare datasets/fiction-retail
  )
fi

load_recipe() {
  local name="$1"
  local dataset_dir="$STATIC_ASSETS_DIR/datasets/$name"

  echo "Loading official DataHub sample: $name"
  (
    cd "$dataset_dir"
    "$DATAHUB_BIN" ingest -c ingest.yaml
    if [[ "$name" == "nyc-taxi" ]]; then
      "$DATAHUB_PYTHON" add_lineage.py --all
      "$DATAHUB_PYTHON" add_metadata.py --all
    else
      "$DATAHUB_PYTHON" add_lineage.py
      "$DATAHUB_PYTHON" add_metadata.py
    fi
  )
}

load_recipe healthcare
load_recipe fiction-retail
load_recipe nyc-taxi

cat <<EOF

Loaded official DataHub sample datasets: NYC Taxi, Healthcare, and Fiction Retail.
Refresh MetaGate at http://127.0.0.1:8765/review to see them in the Hackathon
DataHub assets section. MetaGate discovers the resulting local DataHub URNs;
it does not invent assets for an unloaded recipe.

Recipe cache: $STATIC_ASSETS_DIR
EOF
