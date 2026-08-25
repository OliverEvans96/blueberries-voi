# ADR 0146: EngineSession truth belief for profit oracle

**Status:** ACCEPTED (provisional)  
**Ticket:** oracle-session-parity

## Context

Notebook 17 and Modal profit batch jobs expose a **perfect-information ceiling row**
(`B-state`) beside channel packages (P0–F3). That row previously called
`run_voi_crn_cell` with scenario `"B-state"`, which shares physics RNG with the VOI
CRN cell but uses a **different** episode driver (batch CRN path in `voi.rs`) than the
`EngineSession` closed-loop path used for real channel rows. Waste and stockout were
hard-coded to zero on the Python wrapper even though the episode still incurred spoilage
and missed sales.

Headline channel profit rows already run through `EngineSession` with tuned α, case
rounding, damped-SW policy, and the committed order calendar. The oracle ceiling should
match that stack and differ **only** in belief: policy reads `truth_f_belief` from live
ground truth instead of a particle-filter posterior.

`run_voi_crn_cell` must remain unchanged for M15/VOI sweeps where `"B-state"` is a
scenario arm inside the seven-rung CRN cell.

## Decision

1. Add `BeliefSource::Filter | Truth` on [`EngineSession`](../crates/voi_core/src/session.rs)
   (default `Filter`).
2. When `Truth`:
   - `f_belief_for_policy` and snapshot belief wire use `truth_f_belief(freshness, lot_offsets, k_dim)`.
   - `advance_one` skips `filter_step_unit_with_birth_cached`; rung catch-up is skipped.
   - `init` / `configure` do not seed the particle bank.
3. Wire `belief_source: "filter" | "truth"` through RPC `apply_rpc_configure`, PyO3
   `PyEngineSession::init(belief_source=...)`, and Python `EngineSession.init` config.
4. Rewrite `run_seed_oracle_profit` to `_run_scored_episode` with
   `belief_source="truth"` and `enable_filter=False`. Keep `run_voi_crn_cell` B-state
   untouched.

## Consequences

- Notebook 17 oracle rows align with channel rows on physics, calendar, α, and policy;
  waste/stockout are scored from day logs like other packages.
- VOI CRN `"B-state"` remains the batch research oracle for paired sweeps.
- Studio can opt into truth belief for what-if demos without fabricating observations.
