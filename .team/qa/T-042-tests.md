## Coverage of acceptance criteria

- `controller.ordering.case_round` remains nearest / half-away-from-zero (midpoints 4→8, 12→16; non-midpoints) → `tests/test_audit_t042_case_round.py::test_controller_case_round_midpoints_half_away_from_zero`, `::test_controller_case_round_non_midpoints_match_nearest` — currently **passing** (controller already correct; locks the semantic)
- `sim.episode` has no ceil-to-case; public `case_round` matches controller → `::test_sim_episode_case_round_source_has_no_ceil_arithmetic`, `::test_sim_case_round_matches_controller_on_shared_inputs` — currently failing: episode still implements `np.ceil`
- Disagree band (x=9, case_size=8 → 8) on controller and sim exports → `::test_sim_and_controller_agree_where_ceil_and_nearest_disagree` — currently failing: sim returns 16
- `run_closed_loop_episode` uses nearest on disagreeing band → `::test_closed_loop_orders_use_nearest_not_ceil_on_disagree_band` — currently failing: scored `order_qty=16` (ceil)
- Existing T-026 nearest fixtures still hold on controller → `::test_t026_controller_fixtures_still_exported` — currently **passing**; full `tests/test_ordering.py` remains the suite lock (implement must update/remove any ceil assertions in `tests/test_closed_loop_episode.py`)

## Not covered by tests

- “No production behaviour change outside case-rounding unification” — verify by review / full pytest after implement
- Updating legacy `tests/test_closed_loop_episode.py` ceil expectations (`_case_ceil_units`) — implement ownership when nearest lands (AC says update or remove)

## Notes for implement (T-042)

- Own: `controller/ordering.py` (semantic unchanged), `sim/episode.py` case_round path (re-export / thin wrapper; drop ceil)
- Do **not** edit Abdella / profit / VOI α / MF / stubs (T-043 / T-044)
- Expect `tests/test_closed_loop_episode.py::test_constant_order_policy_scored_order_qty_case_rounded` to break for raw_q=10 (ceil 16 → nearest 8) — update that fixture to nearest
