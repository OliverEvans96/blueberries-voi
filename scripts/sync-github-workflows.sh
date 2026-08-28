#!/usr/bin/env bash
# Copy canonical workflows from packaging/ into live GitHub Actions dir (human integrate step).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WF="$ROOT/.github/workflows"
PKG="$ROOT/packaging/github-workflows"
cd "$ROOT"
for f in ci.yml release-studio.yml studio-preview.yml web-quality.yml rust-kernel.yml; do
  if [[ -f "$PKG/$f" ]]; then
    install -m 644 "$PKG/$f" "$WF/$f"
  fi
done
# Retired T-046 slim Python wheel release (studio-only releases now).
for retired in release-slim-wheel.yml; do
  if [[ -e "$WF/$retired" ]]; then
    rm -f "$WF/$retired"
    echo "Removed retired workflow: $retired"
  fi
done
echo "Synced workflows from packaging/github-workflows/."
