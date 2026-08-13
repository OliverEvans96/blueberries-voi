#!/usr/bin/env bash
# Refresh the Git LFS–tracked pytest-testmon SQLite seed (.testmondata).
# Run from the repo / worktree root after a green implement tip (no coverage).
# Does not auto-commit — stage and commit .testmondata yourself when ready.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f pyproject.toml ]]; then
  echo "error: run from blueberries-voi repo root (pyproject.toml missing)" >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "error: uv is required (https://docs.astral.sh/uv/)" >&2
  exit 1
fi

echo "Refreshing testmon DB (full suite, xdist, no coverage)…"
# Coverage must stay off: --cov forces testmon nocollect and would not update fingerprints.
uv run pytest -n auto --testmon

DB="${ROOT}/.testmondata"
if [[ ! -f "$DB" ]]; then
  echo "error: .testmondata missing after pytest --testmon" >&2
  exit 1
fi

# Detect LFS pointer (agents without git lfs pull) — refuse to "checkpoint" a pointer.
if head -n 1 "$DB" | grep -q '^version https://git-lfs.github.com/spec/v1'; then
  echo "error: .testmondata is a Git LFS pointer, not a SQLite file." >&2
  echo "Run: git lfs install && git lfs pull" >&2
  exit 1
fi

echo "Checkpointing SQLite into a single .testmondata file…"
uv run python -c "
import sqlite3
from pathlib import Path
path = Path('.testmondata')
conn = sqlite3.connect(path)
try:
    conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    conn.execute('PRAGMA journal_mode=DELETE')
    conn.commit()
finally:
    conn.close()
"

# Sidecars should be gone after DELETE mode + checkpoint; never commit them.
rm -f .testmondata-wal .testmondata-shm

echo
echo "Done. Reminder (do not skip if the cache should propagate):"
echo "  git add .testmondata"
echo "  git commit   # include LFS pointer; do not add *-wal / *-shm"
echo
echo "Conflicts: ./scripts/resolve-testmon-conflict.sh ours|theirs"
echo "Verify/CI must still use full cov+xdist without --testmon selection."
