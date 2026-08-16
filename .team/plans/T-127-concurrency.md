# Concurrency plan — T-127

**Parent tip:** `main`
**Peak parallelism:** 5
**Critical path length:** 8 waves

Cockpit Grid layout (Layout 1): fixed 3-row grid with always-on Primary/Secondary/ Economics/Events/Run panes, tuning-dock tab strip; WASM tradeoff_forecast RPC (Options A+B Monte Carlo + joint histogram) and events RPC (masked richest_log window); frontend tradeoff mini-charts and EventsPane with obsMask.ts port.

## Waves

| Wave | Parallel | Tasks |
|------|----------|-------|
| W0 | 1 | architect |
| W1 | 5 | qa-calendar, qa-events-ui, qa-layout, qa-obs-mask, qa-rust-events |
| W2 | 3 | qa-rust-tradeoff, qa-tradeoff-ui, qa-wire |
| W3 | 4 | impl-calendar, impl-layout, impl-obs-mask, impl-rust |
| W4 | 1 | impl-wire |
| W5 | 2 | impl-events-ui, impl-tradeoff-ui |
| W6 | 1 | merge |
| W7 | 1 | changelog |
| W8 | 2 | review, verify |

## Worktree manifest

| Task | Branch | Path |
|------|--------|------|
| `architect` | `team/T-127/architect` | `.worktrees/T-127-architect` |
| `changelog` | `team/T-127/changelog-implement` | `.worktrees/T-127-changelog-implement` |
| `impl-calendar` | `team/T-127/calendar-implement` | `.worktrees/T-127-calendar-implement` |
| `impl-events-ui` | `team/T-127/events-ui-implement` | `.worktrees/T-127-events-ui-implement` |
| `impl-layout` | `team/T-127/layout-implement` | `.worktrees/T-127-layout-implement` |
| `impl-obs-mask` | `team/T-127/obs-mask-implement` | `.worktrees/T-127-obs-mask-implement` |
| `impl-rust` | `team/T-127/rust-implement` | `.worktrees/T-127-rust-implement` |
| `impl-tradeoff-ui` | `team/T-127/tradeoff-ui-implement` | `.worktrees/T-127-tradeoff-ui-implement` |
| `impl-wire` | `team/T-127/wire-implement` | `.worktrees/T-127-wire-implement` |
| `merge` | `team/T-127/merge-implement` | `.worktrees/T-127-merge-implement` |
| `qa-calendar` | `team/T-127/qa` | `.worktrees/T-127-qa-calendar` |
| `qa-events-ui` | `team/T-127/qa` | `.worktrees/T-127-qa-events-ui` |
| `qa-layout` | `team/T-127/qa` | `.worktrees/T-127-qa-layout` |
| `qa-obs-mask` | `team/T-127/qa` | `.worktrees/T-127-qa-obs-mask` |
| `qa-rust-events` | `team/T-127/qa` | `.worktrees/T-127-qa-rust-events` |
| `qa-rust-tradeoff` | `team/T-127/qa` | `.worktrees/T-127-qa-rust-tradeoff` |
| `qa-tradeoff-ui` | `team/T-127/qa` | `.worktrees/T-127-qa-tradeoff-ui` |
| `qa-wire` | `team/T-127/qa` | `.worktrees/T-127-qa-wire` |
| `review` | `team/T-127/review` | `.worktrees/T-127-review` |
| `verify` | `team/T-127/verify` | `.worktrees/T-127-verify` |

## Mermaid

```mermaid
flowchart TB
  architect["architect<br/>W0"]
  style architect fill:#e3f2fd
  qa-rust-tradeoff["qa-rust-tradeoff<br/>W2"]
  style qa-rust-tradeoff fill:#90caf9
  qa-rust-events["qa-rust-events<br/>W1"]
  style qa-rust-events fill:#bbdefb
  qa-obs-mask["qa-obs-mask<br/>W1"]
  style qa-obs-mask fill:#bbdefb
  qa-calendar["qa-calendar<br/>W1"]
  style qa-calendar fill:#bbdefb
  qa-layout["qa-layout<br/>W1"]
  style qa-layout fill:#bbdefb
  qa-tradeoff-ui["qa-tradeoff-ui<br/>W2"]
  style qa-tradeoff-ui fill:#90caf9
  qa-events-ui["qa-events-ui<br/>W1"]
  style qa-events-ui fill:#bbdefb
  qa-wire["qa-wire<br/>W2"]
  style qa-wire fill:#90caf9
  impl-rust["impl-rust<br/>W3"]
  style impl-rust fill:#64b5f6
  impl-obs-mask["impl-obs-mask<br/>W3"]
  style impl-obs-mask fill:#64b5f6
  impl-calendar["impl-calendar<br/>W3"]
  style impl-calendar fill:#64b5f6
  impl-layout["impl-layout<br/>W3"]
  style impl-layout fill:#64b5f6
  impl-wire["impl-wire<br/>W4"]
  style impl-wire fill:#42a5f5
  impl-tradeoff-ui["impl-tradeoff-ui<br/>W5"]
  style impl-tradeoff-ui fill:#2196f3
  impl-events-ui["impl-events-ui<br/>W5"]
  style impl-events-ui fill:#2196f3
  merge["merge<br/>W6"]
  style merge fill:#1e88e5
  changelog["changelog<br/>W7"]
  style changelog fill:#1976d2
  review["review<br/>W8"]
  style review fill:#e3f2fd
  verify["verify<br/>W8"]
  style verify fill:#e3f2fd
  architect --> qa-rust-tradeoff
  architect --> qa-rust-events
  architect --> qa-obs-mask
  architect --> qa-calendar
  architect --> qa-layout
  architect --> qa-tradeoff-ui
  architect --> qa-events-ui
  architect --> qa-wire
  qa-rust-tradeoff --> impl-rust
  qa-rust-events --> impl-rust
  qa-obs-mask --> impl-obs-mask
  qa-calendar --> impl-calendar
  qa-layout --> impl-layout
  impl-rust --> impl-wire
  qa-wire --> impl-wire
  impl-wire --> impl-tradeoff-ui
  qa-tradeoff-ui --> impl-tradeoff-ui
  impl-wire --> impl-events-ui
  impl-obs-mask --> impl-events-ui
  impl-calendar --> impl-events-ui
  qa-events-ui --> impl-events-ui
  impl-layout --> merge
  impl-tradeoff-ui --> merge
  impl-events-ui --> merge
  merge --> changelog
  changelog --> review
  changelog --> verify
```
