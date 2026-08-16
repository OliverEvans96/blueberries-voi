# M1.5 L remeasure + joint→sliding_window fallback (T-015 / ADR 0089)

Addendum to the M1 FIL-13 bakeoff (`fil13_bakeoff.md`, `fil13_scaling.md`) for
**M1.5** open-loop and long-dwell verification cells. Production default remains
**full_joint** (FIL-12=B); this note records re-measured live-cohort **L** and
when the FIL-13 **sliding_window** fallback fires.

## Re-measured L

| Regime | Setting (summary) | Empirical live L | Notes |
| --- | --- | --- | --- |
| M1.5 open-loop (baseline) | M1-like defaults (σ≈0.5, S=60, daily delivery) | p50≈2, max≈3–4 | Same order as M1; joint fits at production K=8, N=2000 for L≤4 |
| Long-dwell Stage A cell | μ=15 + S=120 (slow turn) | p50≈7, max≈7–8 | Pushes past joint budget at prod N; filter must not silently truncate L |

At production **K=8, N=2000**: `joint_state_count` ≤ `MAX_JOINT_FLOATS` for **L≤4**;
**L≥5** trips the budget (`8^5·2000 ≈ 6.55e7 > 5e7`).

## Fallback behaviour

`choose_backend(K, L, N)` / ResearchParticleFilter construct + `initialize(L=…)`:

1. **Within budget** → keep **`full_joint`**, use the configured / empirical **L**
   (dynamic L; not clamped to legacy `PRODUCTION_L=3` when a larger L is safe).
2. **Over budget** → auto-select **`sliding_window`** (bakeoff window default = 3),
   preserve requested **L**, and record a structured reason
   `{K, L, N, joint_floats, backend="sliding_window", reason=…}`.
3. **Never** shrink L to keep joint under budget (FIL-13 guard).

This does **not** reopen FIL-12 toward mean-field; sliding_window is the
pre-approved FIL-13 fallback for long-dwell / high-L cells so Stage A can run.

## See also

- ADR 0089 — Dynamic L + joint→sliding_window fallback
- ADR 0082 / FIL-13 bakeoff — production `full_joint` lock
- `experiments/fil11_stage_a_scenarios.md` — long-dwell knobs (μ15+S120 → L≈7–8)
