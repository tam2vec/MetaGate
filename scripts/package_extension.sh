#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
OUT="$ROOT/dist/MetaGate-DataHub-extension.zip"
mkdir -p "$ROOT/dist"
rm -f "$OUT"
cd "$ROOT/examples/browser-extension"
zip -q -j "$OUT" manifest.json metagate-datahub-panel.js options.html options.js README.md
printf 'Install: chrome://extensions -> Developer mode -> Load unpacked -> examples/browser-extension\n'
printf 'Created %s\n' "$OUT"
