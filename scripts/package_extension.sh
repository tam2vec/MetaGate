#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
OUT="$ROOT/dist/Predicate-DataHub-extension.zip"
mkdir -p "$ROOT/dist"
rm -f "$OUT"
cd "$ROOT/examples/browser-extension"
zip -q -j "$OUT" manifest.json predicate-datahub-panel.js options.html options.js README.md
printf 'Created %s\n' "$OUT"
