# ADR 0148: Controller session step loop (Option A)

**Status:** ACCEPTED (provisional)  
**Ticket:** T-controller-notebook

## Context

Notebook authors and library users need a **Python controller loop** that drives the
production `EngineSession` / Rust kernel without routing through the legacy
`sim.episode.run_closed_loop_episode` path. That episode driver builds oracle beliefs,
uses a different `Policy` protocol (`order(day, belief, …)`), and historically applied
**nearest** `case_round` on closed-loop orders (ADR 0104). Production `EngineSession`
step/act already lives in `voi_core` with filter beliefs on the wire.

Two closed-loop shapes therefore coexist:

| Path | Belief source | Order API | Case round on loop |
|------|---------------|-----------|-------------------|
| **Option A** (`controller.session_loop`) | Filter wire from `snapshot` | `controller.order(ControllerContext)` | Policy / controller chooses int; session enforces schedule in Rust |
| **Episode.py** (`run_closed_loop_episode`) | Oracle cohort rebuild | `policy.order(day, belief, …)` | Nearest via shared `sim.case_round` |

Teaching notebooks should use **Option A only** so readers learn the same stack as Studio
and Modal profit jobs.

## Decision

1. Add `controller.session_loop` with:
   - `default_session_config()` defaulting to `smoke_cool_shipments()`
   - `context_from_snapshot` / `pipeline_wire_to_pending`
   - `run_controller_session(session, controller, n_days)` implementing
     `snapshot → order → step` with optional `LearningController.observe`
   - `PolicyController` adapter for `CorrectedAgeBlindPolicy` and
     `DampedSurvivalWeightedPolicy`
2. Add `EngineSession.snapshot()` delegating to PyO3 `snapshot_value()` + `_coerce_snapshot`.
3. Add `controller.starter` with `NaiveBaseStockController` and tabular Q-learning starter.
4. Notebook `19_build_your_own_controller.ipynb` uses Option A; paired-seed benchmarks compare
   custom controllers to production `act(policy="damped_sw")` only — **do not** teach
   `run_closed_loop_episode` or rollout autopilot.
5. **Rounding:** Option A policies call `sim.case_round` (nearest, ADR 0104). Episode.py
   closed-loop must keep the same nearest semantic when updated; divergent ceil rounding
   on the episode path remains a known audit item (T-042), not introduced on Option A.

## Consequences

- Custom controllers share belief wire and schedule gates with production session.
- Episode.py remains for M2 ladder / α-tune until a later migration ticket.
- Tests lock wire coercion without Rust; Rust tests lock constant-order and schedule gates.
