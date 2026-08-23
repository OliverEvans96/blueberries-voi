# Concurrency plan — T-158

**Parent tip:** `main`
**Peak parallelism:** 2
**Critical path length:** 6 waves

Layout v7 — move tuning dock to right-side TuningDrawer (gear trigger), single-row cockpit grid metrics | belief | sidebar, 2-column interleaved drawer interior.

## Waves

| Wave | Parallel | Tasks |
|------|----------|-------|
| W0 | 1 | architect |
| W1 | 1 | qa-red |
| W2 | 2 | impl-drawer, impl-shell-grid |
| W3 | 2 | impl-interleave, impl-studio-logic |
| W4 | 1 | impl-version-tests |
| W5 | 2 | review, verify |

## Worktree manifest

| Task | Branch | Path |
|------|--------|------|
| `architect` | `team/T-158/architect` | `.worktrees/T-158-architect` |
| `impl-drawer` | `team/T-158/drawer-implement` | `.worktrees/T-158-drawer-implement` |
| `impl-interleave` | `team/T-158/interleave-implement` | `.worktrees/T-158-interleave-implement` |
| `impl-shell-grid` | `team/T-158/shell-grid-implement` | `.worktrees/T-158-shell-grid-implement` |
| `impl-studio-logic` | `team/T-158/studio-logic-implement` | `.worktrees/T-158-studio-logic-implement` |
| `impl-version-tests` | `team/T-158/version-tests-implement` | `.worktrees/T-158-version-tests-implement` |
| `qa-red` | `team/T-158/qa` | `.worktrees/T-158-qa-red` |
| `review` | `team/T-158/review` | `.worktrees/T-158-review` |
| `verify` | `team/T-158/verify` | `.worktrees/T-158-verify` |

## Mermaid

```mermaid
flowchart TB
  architect["architect<br/>W0"]
  style architect fill:#e3f2fd
  qa-red["qa-red<br/>W1"]
  style qa-red fill:#bbdefb
  impl-drawer["impl-drawer<br/>W2"]
  style impl-drawer fill:#90caf9
  impl-shell-grid["impl-shell-grid<br/>W2"]
  style impl-shell-grid fill:#90caf9
  impl-studio-logic["impl-studio-logic<br/>W3"]
  style impl-studio-logic fill:#64b5f6
  impl-interleave["impl-interleave<br/>W3"]
  style impl-interleave fill:#64b5f6
  impl-version-tests["impl-version-tests<br/>W4"]
  style impl-version-tests fill:#42a5f5
  review["review<br/>W5"]
  style review fill:#2196f3
  verify["verify<br/>W5"]
  style verify fill:#2196f3
  architect --> qa-red
  qa-red --> impl-drawer
  qa-red --> impl-shell-grid
  impl-drawer --> impl-studio-logic
  impl-shell-grid --> impl-studio-logic
  impl-drawer --> impl-interleave
  impl-studio-logic --> impl-version-tests
  impl-interleave --> impl-version-tests
  impl-version-tests --> review
  impl-version-tests --> verify
```
