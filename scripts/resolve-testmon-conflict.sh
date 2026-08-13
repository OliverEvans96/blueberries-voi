#!/usr/bin/env bash
# Resolve a .testmondata merge conflict by taking one side (disposable cache).
# Usage: ./scripts/resolve-testmon-conflict.sh ours|theirs
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SIDE="${1:-}"
if [[ "$SIDE" != "ours" && "$SIDE" != "theirs" ]]; then
  echo "usage: $0 ours|theirs" >&2
  echo "Never hand-merge .testmondata — take one blob and continue." >&2
  exit 2
fi

if [[ ! -f .testmondata ]] && ! git ls-files -u -- .testmondata | grep -q .; then
  echo "error: no .testmondata conflict staged (nothing to resolve)" >&2
  exit 1
fi

git checkout "--${SIDE}" -- .testmondata
git add .testmondata
echo "Staged .testmondata from --${SIDE}. Continue the merge/rebase as usual."
echo "Optional: re-run ./scripts/refresh-testmon.sh after the merge completes."
