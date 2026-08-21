# T-136 RED test map

| AC | Test | Expected RED reason |
|----|------|---------------------|
| Deterministic P1 (no MC in weight) | `p1_totals_loglik_deterministic_no_path_mc_in_body` | body still calls `sequential_kernel_path_logprob` |
| F1 multinomial cross-lot term | `loglik_sales_by_units_uses_multinomial_cross_lot_term` | no `multinomial`/`lot_share` in unit_ll.rs |
| `p1_totals_loglik` no rng | `p1_totals_loglik_impossible_sales_neg_inf` | compile error (extra rng arg) |
| Mutable path kernel | `sequential_kernel_path_logprob_feasible_finite` | compile error + no mutation |
| State mutation after finite ll | `score_particle_mutates_freshness_after_finite_p1_ll` | sold units not removed |
| F1 MAE ≤ P1 MAE | `unit_pf_f1_p1_relative_mean_f_mae` | F1 noisier than P1 today |
| F1 strictly beats P1 heterogeneous | `unit_pf_f1_strictly_beats_p1_heterogeneous_lots` | no cross-lot scoring |
| Multinomial approx small L | `multinomial_vs_exact_wor_split_small_l` | math validation (may pass) |
| Multinomial approx realistic L | `multinomial_vs_wor_mc_realistic_l` | math validation (may pass) |

RED proof command:

```bash
cargo test -p voi_core --test unit_pf_ac -- --exact \
  p1_totals_loglik_impossible_sales_neg_inf \
  p1_totals_loglik_deterministic_no_path_mc_in_body \
  loglik_sales_by_units_uses_multinomial_cross_lot_term \
  sequential_kernel_path_logprob_feasible_finite \
  score_particle_mutates_freshness_after_finite_p1_ll \
  unit_pf_f1_p1_relative_mean_f_mae \
  unit_pf_f1_strictly_beats_p1_heterogeneous_lots
```

> **Superseded by ADR 0137.** `p1_totals_loglik` and the binomial waste primitives were
> removed from `unit_ll`; the test names in the table above no longer exist. The contracts
> they pinned (deterministic weight, no rng, no MC path in the weight) now live in
> `production_likelihood_terms_take_no_rng`,
> `production_likelihood_terms_have_no_path_mc_in_body`, and
> `aggregate_totals_weight_rejects_infeasible_sales` in `crates/voi_core/tests/unit_pf_ac.rs`.
