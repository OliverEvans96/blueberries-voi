# 0122. Studio episodes accumulate full history and hard-stop at day 90

STATUS: ACCEPTED
DATE: 2026-08-14
RELATED: ADR 0100 (export contract; history append/drop clause), ADR 0110 (obs_scenario still reset-gated until the caches ticket)

## Context

ADR 0100 split ownership so Python emits DayDelta and JS mirrors a **history window append / drop**.
The studio implemented that as a 14-day rolling series (`window_days`, `drop_oldest`, projector
`drop_oldest` / length cap). That window was a chart convenience, not a physics limit. Operators
need episode-length charts and PnL, then a clean stop at the VOI-shaped 90-day horizon, not a
sliding KPI.

A later ticket will keep a richest observation log for mid-episode knowledge-scenario catch-up.
This decision only freezes **length and truncation**: thin history may stay thin.

## Decision

We will:

1. Treat a studio run as one **episode of at most 90 days**. History is days `0…t` until the cap.
   Python and JS **never drop** oldest days until Reset. `DayDelta.drop_oldest` remains on the
   wire and is **always false**.
2. Drive charts, sales/inventory series, and `pnl_totals` from that full series. Ghost-vs-last-reset
   compares two full episodes (or the overlapping prefix if the previous run was shorter).
3. When `episode_day == 90`, **do not Advance** (and pause Autopilot). Show that the episode
   finished and **Reset** starts another. The 90-day mark is an episode end, not a sliding window.
4. Remove `window_days` as a user-facing rolling knob. Episode length 90 is the cap, not a chart
   window. Reset still clears physics and history; other SimConfig knobs stay dirty-until-Reset.

## Alternatives considered

- **Keep a 14-day rolling chart window while physics runs to 90** — rejected: totals and charts
  would still lie about the episode, which is the product bug.
- **Uncapped episodes** — rejected: Autopilot + filter cost grows without bound in the browser;
  90 already matches the VOI burn+score shape and existing benches.
- **Drop `drop_oldest` from DayDelta** — rejected this ticket: schema tests and hosts already
  require the key; always-false preserves the contract without a breaking rename.

## Consequences

**Easy:** PnL and plots match the run the user just played; Reset is an obvious next action at day 90.

**Hard / cost:** Snapshots carry up to 90 thin day dicts (kilobytes). Callers that assumed a max
length of 14 must update. Autopilot must notice the cap and pause instead of retrying `act`.

**Locked in:** no rolling drop until Reset; refuse step/act/step_n at day ≥ 90 on the Python
session; UI copy points at Reset.

**Revisit if:** a later ticket stores richest logs / per-rung filters (still capped at 90), or
Rust/wasm must refuse the same cap for parity.
