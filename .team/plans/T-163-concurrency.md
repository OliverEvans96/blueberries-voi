# Concurrency plan — T-163

**Parent tip:** `team/arrival-breaks/integrate`
**Peak parallelism:** 5
**Critical path length:** 10 waves

PR #65 finish — Stage 1 transit generative v2 (bottom-up Abdella stages, trip modes, hourly OU, 0150 breaks, filter projection), Stage 2 multi-lot L=3 birth wiring, Stage 3 Python/TS/wire mirrors + version bump + docs code-ref re-pins.

## Waves

| Wave | Parallel | Tasks |
|------|----------|-------|
| W0 | 1 | architect |
| W1 | 5 | qa-mirrors, qa-multilot, qa-v2-artifact, qa-v2-filter, qa-v2-generative |
| W2 | 1 | qa-v2-guards |
| W3 | 1 | impl-artifact-fit |
| W4 | 1 | impl-generative-path |
| W5 | 1 | impl-filter-projection |
| W6 | 1 | impl-session-studio |
| W7 | 1 | impl-multilot-wiring |
| W8 | 1 | impl-mirrors |
| W9 | 1 | impl-version-citations |
| W10 | 2 | review, verify |

## Worktree manifest

| Task | Branch | Path |
|------|--------|------|
| `architect` | `team/T-163/architect` | `.worktrees/T-163-architect` |
| `impl-artifact-fit` | `team/T-163/artifact-fit-implement` | `.worktrees/T-163-artifact-fit-implement` |
| `impl-filter-projection` | `team/T-163/filter-projection-implement` | `.worktrees/T-163-filter-projection-implement` |
| `impl-generative-path` | `team/T-163/generative-path-implement` | `.worktrees/T-163-generative-path-implement` |
| `impl-mirrors` | `team/T-163/mirrors-implement` | `.worktrees/T-163-mirrors-implement` |
| `impl-multilot-wiring` | `team/T-163/multilot-wiring-implement` | `.worktrees/T-163-multilot-wiring-implement` |
| `impl-session-studio` | `team/T-163/session-studio-implement` | `.worktrees/T-163-session-studio-implement` |
| `impl-version-citations` | `team/T-163/version-citations-implement` | `.worktrees/T-163-version-citations-implement` |
| `qa-mirrors` | `team/T-163/qa` | `.worktrees/T-163-qa-mirrors` |
| `qa-multilot` | `team/T-163/qa` | `.worktrees/T-163-qa-multilot` |
| `qa-v2-artifact` | `team/T-163/qa` | `.worktrees/T-163-qa-v2-artifact` |
| `qa-v2-filter` | `team/T-163/qa` | `.worktrees/T-163-qa-v2-filter` |
| `qa-v2-generative` | `team/T-163/qa` | `.worktrees/T-163-qa-v2-generative` |
| `qa-v2-guards` | `team/T-163/qa` | `.worktrees/T-163-qa-v2-guards` |
| `review` | `team/T-163/review` | `.worktrees/T-163-review` |
| `verify` | `team/T-163/verify` | `.worktrees/T-163-verify` |

## Mermaid

```mermaid
flowchart TB
  architect["architect<br/>W0"]
  style architect fill:#e3f2fd
  qa-v2-artifact["qa-v2-artifact<br/>W1"]
  style qa-v2-artifact fill:#bbdefb
  qa-v2-generative["qa-v2-generative<br/>W1"]
  style qa-v2-generative fill:#bbdefb
  qa-v2-filter["qa-v2-filter<br/>W1"]
  style qa-v2-filter fill:#bbdefb
  qa-v2-guards["qa-v2-guards<br/>W2"]
  style qa-v2-guards fill:#90caf9
  qa-multilot["qa-multilot<br/>W1"]
  style qa-multilot fill:#bbdefb
  qa-mirrors["qa-mirrors<br/>W1"]
  style qa-mirrors fill:#bbdefb
  impl-artifact-fit["impl-artifact-fit<br/>W3"]
  style impl-artifact-fit fill:#64b5f6
  impl-generative-path["impl-generative-path<br/>W4"]
  style impl-generative-path fill:#42a5f5
  impl-filter-projection["impl-filter-projection<br/>W5"]
  style impl-filter-projection fill:#2196f3
  impl-session-studio["impl-session-studio<br/>W6"]
  style impl-session-studio fill:#1e88e5
  impl-multilot-wiring["impl-multilot-wiring<br/>W7"]
  style impl-multilot-wiring fill:#1976d2
  impl-mirrors["impl-mirrors<br/>W8"]
  style impl-mirrors fill:#e3f2fd
  impl-version-citations["impl-version-citations<br/>W9"]
  style impl-version-citations fill:#bbdefb
  review["review<br/>W10"]
  style review fill:#90caf9
  verify["verify<br/>W10"]
  style verify fill:#90caf9
  architect --> qa-v2-artifact
  architect --> qa-v2-generative
  architect --> qa-v2-filter
  architect --> qa-v2-guards
  architect --> qa-multilot
  architect --> qa-mirrors
  qa-v2-artifact --> impl-artifact-fit
  qa-v2-generative --> impl-generative-path
  impl-artifact-fit --> impl-generative-path
  qa-v2-filter --> impl-filter-projection
  impl-generative-path --> impl-filter-projection
  qa-v2-guards --> impl-session-studio
  impl-filter-projection --> impl-session-studio
  qa-multilot --> impl-multilot-wiring
  impl-session-studio --> impl-multilot-wiring
  qa-mirrors --> impl-mirrors
  impl-multilot-wiring --> impl-mirrors
  impl-mirrors --> impl-version-citations
  impl-version-citations --> review
  impl-version-citations --> verify
```
