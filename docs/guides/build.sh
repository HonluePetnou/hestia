#!/usr/bin/env bash
# Render docs/guides/src/*.html to docs/guides/*.pdf with Edge (or Chrome) headless.
# Usage (Git Bash on Windows): bash docs/guides/build.sh [name-filter]
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
browser="${BROWSER_BIN:-/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe}"
# A dedicated profile keeps headless Edge from attaching to an already-running Edge window.
profile="$(cygpath -w "${TEMP:-/tmp}")\\hestia-pdf-profile"
for src in "$here"/src/*${1:-}*.html; do
  name="$(basename "$src" .html)"
  "$browser" --headless=new --disable-gpu --no-pdf-header-footer --user-data-dir="$profile" \
    --print-to-pdf="$(cygpath -w "$here")\\$name.pdf" "file:///$(cygpath -m "$src")" 2>&1 | grep -o "bytes written.*" || echo "FAILED $name"
done
