# 0098. pytest-testmon with Git LFS–tracked `.testmondata` seed

STATUS: ACCEPTED
DATE: 2026-08-13
BOARD-ID: *(repo)*
GROUP: ENG
PROVENANCE: agent worktree test-efficiency / testmon LFS cache plan
TIER: 2
MILESTONE: process — implement fast loops

## Context

Agent role worktrees often re-run large slices of an already-green suite. **pytest-testmon** fingerprints
dependencies and deselects tests that cannot be affected by local edits, which speeds implement
red/green loops. Worktrees need a shared seed so each new tip does not rebuild the SQLite DB from
scratch. Coverage collection forces testmon into nocollect mode, so verify/CI cannot be the refresh
path. This repo already uses Git LFS for binary assets; the same mechanism can carry a best-effort
`.testmondata` blob across branches and worktrees.

## Decision

We will:

1. Add **pytest-testmon** as a **dev** optional dependency.
2. Track **`.testmondata`** via **Git LFS** as a best-effort cache seed (not a correctness artifact).
3. Refresh the DB only after a green **no-coverage** full run:
   `uv run pytest -n auto --testmon` (see `scripts/refresh-testmon.sh`), then SQLite
   `wal_checkpoint(TRUNCATE)` + `journal_mode=DELETE` so only a single file is committed.
4. Keep default `pytest` / `addopts` free of `--testmon` and `--cov` (ADR 0097).
5. Keep verify/CI as an honest full suite with coverage + xdist; they must **not** rely on testmon
   deselection for the gate (use `--no-testmon` if `addopts` ever gains `--testmon`).

Ignore `.testmondata-wal` and `.testmondata-shm`. Never auto-commit the DB; print a reminder after
refresh. On merge conflict, take ours or theirs — never hand-merge SQLite.

## Alternatives considered

- **Shared out-of-git SQLite across concurrent worktrees** — rejected: races and unclear ownership
  across parallel tickets.
- **Verify-time collect under `--cov`** — rejected: coverage forces testmon nocollect; would not
  refresh fingerprints honestly.
- **Binary merge of SQLite / custom 3-way merge driver** — rejected: disposable cache; take one side.
- **`--testmon` in default `addopts`** — rejected: surprises qa RED proofs and partial `-k` runs.
- **Plugin verifier allowlist for `.testmondata` (MVP)** — deferred: implement tip refresh seeds
  children; expanding agent-dev-team verify commit allowlist is optional later.

## Consequences

**Easy:** Implement loops can opt into `pytest --testmon` and inherit fingerprints via LFS after a
seeded tip; refresh script checkpoints a single-file DB.  
**Hard:** Agents without Git LFS may see a pointer file (fallback: full collect); env/Python drift
can invalidate selection; parallel tickets may conflict on the blob (resolve by taking one side).  
**Locked:** `pytest-testmon` is a `[dev]` dependency; `.testmondata` is LFS-tracked; WAL/SHM stay
gitignored; verify/CI remain full cov+xdist without testmon selection.  
**Revisit if:** LFS pointer friction or conflict noise exceeds savings — then drop the committed seed
and keep testmon local-only, or move refresh ownership to verify via a plugin allowlist change.
