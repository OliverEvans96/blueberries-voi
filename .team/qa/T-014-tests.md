# T-014 test map (post-GREEN)

- When `sales_by_lot` is present (F1 / F2), LL uses per-lot sales; lot-A update moves lot A’s age/count posterior more than lot B (cross-lot leakage bound) → `tests/test_lot_resolved_ll.py::test_observation_loglik_mc_scores_sales_by_lot_when_present` — **PASS**
- Same AC (RBPF age posterior + leakage) → `tests/test_lot_resolved_ll.py::test_sales_by_lot_update_targets_lot_a_more_than_lot_b_leakage_bound` — **PASS**
- Same AC (count-posterior proxy) → `tests/test_lot_resolved_ll.py::test_sales_by_lot_shifts_count_posterior_toward_observed_lot` — **PASS**
- When `waste_by_lot` is present (F1s / F2), per-lot waste scored → `tests/test_lot_resolved_ll.py::test_observation_loglik_mc_scores_waste_by_lot_when_present` — **PASS**
- Waste cross-lot leakage → `tests/test_lot_resolved_ll.py::test_waste_by_lot_update_targets_lot_a_more_than_lot_b_leakage_bound` — **PASS**
- UNOBSERVED maps match totals-only (P0/P1) → `tests/test_lot_resolved_ll.py::test_unobserved_lot_maps_match_totals_only_scoring` — **PASS**
- No empty-map conditioning (`{}` ≠ UNOBSERVED) → `tests/test_lot_resolved_ll.py::test_empty_observed_sales_by_lot_not_scored_like_unobserved` — **PASS**
- F1 rho=1 complete DayLog maps → `tests/test_lot_resolved_ll.py::test_f1_default_rho_one_sales_by_lot_complete_for_sold_lots` — **PASS**
- Biased-rho absent / non-gate → `tests/test_lot_resolved_ll.py::test_biased_rho_sampler_absent_or_marked_non_gate` — **PASS**
- One RBPF / one MC LL entrypoint → `tests/test_lot_resolved_ll.py::test_single_rbpf_class_and_one_mc_ll_entrypoint` — **PASS**
