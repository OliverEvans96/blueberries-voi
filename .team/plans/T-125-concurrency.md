# Concurrency plan — T-125

**Parent tip:** `main`
**Peak parallelism:** 4
**Critical path length:** 6 waves

Retire Pyodide + HTTP API; WASM-only browser studio (ADR 0129)

## Warnings
- task integration-merge: empty files list (cannot detect conflicts)

## Waves

| Wave | Parallel | Tasks |
|------|----------|-------|
| W0 | 1 | architect |
| W1 | 3 | qa-guards, qa-hydrate-obs, qa-studio |
| W2 | 4 | impl-api, impl-config, impl-pyodide, impl-studio |
| W3 | 3 | impl-closeout, impl-docs, impl-hydrate-obs |
| W4 | 1 | integration-merge |
| W5 | 2 | review, verify |

## Worktree manifest

| Task | Branch | Path |
|------|--------|------|
| `architect` | `team/T-125/architect` | `.worktrees/T-125-architect` |
| `impl-api` | `team/T-125/api-implement` | `.worktrees/T-125-api-implement` |
| `impl-closeout` | `team/T-125/closeout-implement` | `.worktrees/T-125-closeout-implement` |
| `impl-config` | `team/T-125/config-implement` | `.worktrees/T-125-config-implement` |
| `impl-docs` | `team/T-125/docs-implement` | `.worktrees/T-125-docs-implement` |
| `impl-hydrate-obs` | `team/T-125/hydrate-obs-implement` | `.worktrees/T-125-hydrate-obs-implement` |
| `impl-pyodide` | `team/T-125/pyodide-implement` | `.worktrees/T-125-pyodide-implement` |
| `impl-studio` | `team/T-125/studio-implement` | `.worktrees/T-125-studio-implement` |
| `integration-merge` | `team/T-125/integration-merge` | `.worktrees/T-125-integration-merge` |
| `qa-guards` | `team/T-125/qa` | `.worktrees/T-125-qa-guards` |
| `qa-hydrate-obs` | `team/T-125/qa` | `.worktrees/T-125-qa-hydrate-obs` |
| `qa-studio` | `team/T-125/qa` | `.worktrees/T-125-qa-studio` |
| `review` | `team/T-125/review` | `.worktrees/T-125-review` |
| `verify` | `team/T-125/verify` | `.worktrees/T-125-verify` |

## Mermaid

```mermaid
flowchart TB
  architect["architect<br/>W0"]
  style architect fill:#e3f2fd
  qa-guards["qa-guards<br/>W1"]
  style qa-guards fill:#bbdefb
  qa-studio["qa-studio<br/>W1"]
  style qa-studio fill:#bbdefb
  qa-hydrate-obs["qa-hydrate-obs<br/>W1"]
  style qa-hydrate-obs fill:#bbdefb
  impl-pyodide["impl-pyodide<br/>W2"]
  style impl-pyodide fill:#90caf9
  impl-api["impl-api<br/>W2"]
  style impl-api fill:#90caf9
  impl-studio["impl-studio<br/>W2"]
  style impl-studio fill:#90caf9
  impl-config["impl-config<br/>W2"]
  style impl-config fill:#90caf9
  impl-hydrate-obs["impl-hydrate-obs<br/>W3"]
  style impl-hydrate-obs fill:#64b5f6
  impl-closeout["impl-closeout<br/>W3"]
  style impl-closeout fill:#64b5f6
  impl-docs["impl-docs<br/>W3"]
  style impl-docs fill:#64b5f6
  integration-merge["integration-merge<br/>W4"]
  style integration-merge fill:#42a5f5
  review["review<br/>W5"]
  style review fill:#2196f3
  verify["verify<br/>W5"]
  style verify fill:#2196f3
  architect --> qa-guards
  architect --> qa-studio
  architect --> qa-hydrate-obs
  qa-guards --> impl-pyodide
  qa-guards --> impl-api
  qa-studio --> impl-studio
  qa-guards --> impl-config
  impl-pyodide --> impl-hydrate-obs
  impl-api --> impl-hydrate-obs
  qa-hydrate-obs --> impl-hydrate-obs
  impl-pyodide --> impl-closeout
  impl-api --> impl-closeout
  qa-guards --> impl-closeout
  impl-pyodide --> impl-docs
  impl-api --> impl-docs
  impl-studio --> impl-docs
  impl-config --> impl-docs
  impl-hydrate-obs --> integration-merge
  impl-closeout --> integration-merge
  impl-docs --> integration-merge
  integration-merge --> review
  integration-merge --> verify
```
