# M2.5 Stage B — multi-rung calibration + oracle ladder

Library: `blueberries_voi.viz.m25.run_m25_stage_b` / `run_m25_oracle_ladder` (T-017).
Shared `root_seed=0`; only the observation mask differs by rung.

## Pass language

Stage B PASS when 90% CI coverage lies in [0.7, 0.99] around nominal 90% and ranks are not strongly U-shaped or dome-shaped. On rungs that Stage A failed, Stage B is diagnostic only (same pattern as M1 post-A-fail).

- Coverage band: [0.7, 0.99] around nominal 90%.
- Rank rule: Rank histogram of the true age under the posterior must not be strongly U-shaped (mass at 0 and 1) or dome-shaped (mass piled near 0.5); prefer near-flat ranks with mean near 0.5 and modest std (visual + numeric).

## Per-rung Stage B

| rung | coverage_90 | diagnostic_only | figure |
| --- | --- | --- | --- |
| P0 | 1.0000 | yes — diagnostic only — Stage A fail (or unmarked); calibration evidence only, not a Stage B gate reopen | `m25_stage_b_P0_rank.png` |
| P1 | 1.0000 | yes — diagnostic only — Stage A fail (or unmarked); calibration evidence only, not a Stage B gate reopen | `m25_stage_b_P1_rank.png` |
| F1 | 0.8750 | yes — diagnostic only — Stage A fail (or unmarked); calibration evidence only, not a Stage B gate reopen | `m25_stage_b_F1_rank.png` |
| F1s | 1.0000 | yes — diagnostic only — Stage A fail (or unmarked); calibration evidence only, not a Stage B gate reopen | `m25_stage_b_F1s_rank.png` |
| F2a | 1.0000 | yes — diagnostic only — Stage A fail (or unmarked); calibration evidence only, not a Stage B gate reopen | `m25_stage_b_F2a_rank.png` |
| F2 | 0.0000 | no | `m25_stage_b_F2_rank.png` |

P0/P1 (and any other Stage A fail) runs are **diagnostic only** — evidence, not a gate reopen.

**Postscript (T-019):** Stage A F2a now **contracts / PASS**
(`experiments/m25_stage_a_result.md`). The F2a `diagnostic_only` row above is
the pre-pack_date-emit Stage B publication; regenerate with
`stage_a_pass={'F2a': True, 'F2': True}` when refreshing calibration evidence.
Coverage numbers above are unchanged until that republish.

## Oracle ladder (shared CRN vs B-state)

B-state sets belief to true `(n, τ)` (filter bypass); age error is zero by construction. Compare defaults: P1 vs F2.

| scenario | mean_abs_age_error | vs_b_state |
| --- | --- | --- |
| P1 | 1.5412 | 1.5412 |
| F2 | 0.3431 | 0.3431 |

Gap check: F2 << P1 vs B-state (max ratio 0.5) — **PASS**.
