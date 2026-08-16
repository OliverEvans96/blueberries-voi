# T-C2-A Review

**Verdict:** APPROVED  
**Reviewer role:** review  
**Branch reviewed:** `team/feature-c2-a-f-native/integration-merge`  
**Spec:** `.team/specs/T-C2-A.md`  
**ADR:** `.team/adr/0130-f-native-c2-a-unit-pf.md`

## Summary

The integration merge delivers f-native C2 Algorithm A end-to-end: `unit_day_step` ground truth, `filter_step_unit` with sales_by-when-available / P1 totals routing, `belief_flat_from_unit_bank` (`f_grid` / `f_marginals`), f-native damped-SW policy, Python schema + PyO3 wire, and frontend f-marginals migration. ADR 0130 supersession of 0105/0106 production semantics is reflected in code and updated tests.

## Acceptance criteria

| AC group | Status | Notes |
|----------|--------|-------|
| AC-daystep | PASS | Gamma on f, spoil f≤0, `picking_weights_f`, delivery birth-f |
| AC-unit-pf | PASS | `unit_ll` + `unit_pf`, obs router, L=20 accuracy gate |
| AC-belief | PASS | `belief_flat_from_unit_bank`, f-wire export |
| AC-policy | PASS | `effective_inventory_f_belief`, `damped_sw_order_f_belief` |
| AC-session | PASS | Session/VOI/catch-up on unit PF; `units_per_lot` configure |
| AC-python-wire | PASS | Schema, goldens, rust session wire tests |
| AC-frontend | PASS | FlatBelief f fields, projector, inventory E[f] bands |
| AC-bench-cleanup | PASS | Benches use production modules; hot path Weibull removed |
| AC-guards | PASS | Legacy τ-wire tests updated or gated |

## Findings

No blocking issues. Minor notes (non-blocking):

- `test_rust_parity` trajectory check relaxed to f-native wire shape (transient zero `lot_counts` after large orders is expected under unit-f filter).
- Timing-freshness experiment scripts not on main were dropped from merge to keep ruff clean; study markdown + `generate_c2_a_totals_report.py` retained.

## Decision

**APPROVED** for verify / human integrate.
