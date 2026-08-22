# 0141. Unified gamma-in-warped-time arrival model (Stage C)

STATUS: SUPERSEDED BY 0144
DATE: 2026-08-21
TICKET: T-140
SUPERSEDED BY: [0144](./0144-f-native-hierarchical-arrival-model.md) (T-150) — same gamma-in-
warped-time idea, but drawn in f-space with no `eta_ref` division, with `d` / `T_bar` from a
committed hierarchical artifact instead of a fleet-trace bootstrap, and with `gamma_scale`
recalibrated so `k·θ·η_ref = 1`.
RELATED: [0133](./0133-observation-channel-toggles.md) (delivery_history ladder),
[0139](./0139-heterogeneous-arrivals-within-lot-dispersion.md) (Stage A dispersion — superseded birth law),
[0131](./0131-f-native-wire-tau-retirement.md) (F2a Gaussian on τ — retired),
MOD-11 (transit temperature model)

## Context

The heterogeneity stack (T-138/T-139) added within-lot spread via `arrival_dispersion_sd` and a
truncated Normal on freshness, while F2a still used hand-set `f2a_transit_uncertainty_sd = 0.75` on
rounded warped age. Diagnostic analysis (notebook 14 / Stage C plan) showed:

1. **F2→F3 gain is partly artifact** — pack date emits `round(τ)` (warped age), scored against σ=0.75
   when true rounding residual sd ≈ 0.29.
2. **`mix_arrival_f` ignores session fleet** — hard-coded 3-trace bootstrap in `unit_pf.rs`.
3. **Isothermal fleet** — every trace at 1 °C makes φ̄ degenerate; temperature history cannot buy
   information over calendar pack date under honest physics.

Stage C unifies arrival under one generative object: **Gamma subordinator in Q10-warped time**.

## Decision

**Stage C (T-140)** adopts:

1. **Warped duration** — `Λ = ∫ q10^((T(t)−T_ref)/10) dt` via existing `arrival_age_from_path`;
   **calendar duration** `d = times.last − times.first` for pack-date channel.

2. **Per-unit transit age** — `age_i ~ Gamma(k·Λ, θ)` with `k = gamma_shape`, `θ = gamma_scale`
   (same shelf aging parameters). Freshness `f_i = age_to_f(age_i, η_ref)`. Aleatoric σ_within =
   `θ√(kΛ)` — derived, not a free knob.

3. **φ̄ temperature prior** — for each fleet trace `φ̄_s = Λ_s / d_s`. Pack-date channel:
   `Λ = d_obs · φ̄` with `φ̄` drawn from empirical fleet (bootstrap index). Temperature history:
   `Λ` exact from trace; still per-unit Gamma draws (F3 is not Dirac).

4. **Calendar pack_date** — wire `pack_date_days = round(d)`, not `round(τ)`. Supersedes ADR 0131
   F2a Gaussian formula.

5. **Deletions** — remove `f2a_transit_uncertainty_sd`, `mix_arrival_f`, F2a Gaussian birth path,
   and production use of truncated-Normal `birth_f_units` (keep test helper or replace with gamma).

6. **Thermal fleet** — `shipments_thermal()` in diag: fixed duration, varying temperature so φ̄
   disperses and F2→F3 contrast is physically meaningful.

## Alternatives considered

- **Tune σ to 0.289 (rounding only)** — rejected; does not unify σ_within/σ_epistemic or fix
  calendar vs warped pack date.
- **Keep `arrival_dispersion_sd` alongside gamma** — rejected; double-counts aleatoric spread.
- **Dirac F3 under gamma model** — rejected; removes within-lot variation at top rung.

## Consequences

- ADR 0131 F2a row and `f2a_transit_uncertainty_sd` default superseded.
- ADR 0139 aleatoric layer via `arrival_dispersion_sd` superseded on production birth path.
- ADR 0133: `delivery_history` ladder is variance decomposition; update orthogonality footnote.
- Studio drops `f2a_transit_sd` slider; arrival prior chart uses fleet φ̄.
- Isothermal fleets: ladder correctly collapses at top rung (pack date sufficient).
- Notebook 14 must regen matched before/after at new physics (CRN not comparable across epochs).
