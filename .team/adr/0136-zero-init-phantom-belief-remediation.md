# 0136. Zero-init episodes and phantom-belief remediation

STATUS: PROPOSED
DATE: 2026-08-20
BOARD-ID: FIL
GROUP: FIL
PROVENANCE: T-137 — UPC vs LGTIN belief parity / empty-shelf init
TIER: 1
RELATED: [0130](./0130-f-native-c2-a-unit-pf.md), [0135](./0135-unify-p1-f1-sales-likelihood.md)

## Context

Production filter init pre-fills every particle with `L × units_per_lot` random freshness while physics starts empty, producing ~20+ units of belief mass on an empty shelf. P1 aggregate totals collapse this quickly; LGTIN per-lot scoring is uninformative on zero-sales days (length mismatch or LL=0). Studio mock exposes `starting_inv` (mock-only) while Rust ignores it.

## Decision

1. **Global zero-init:** Episodes begin with empty physics shelf and empty filter bank; `sum(lot_counts)==0` at init. Inventory enters only via arrivals after orders.
2. **Remove `starting_inv`** from studio `SimConfig` and mock `buildStartingLots`.
3. **LGTIN zero-sales parity:** `align_lot_map` on sales path; when `sales_tot==0`, apply shared aggregate constraint (binomial waste gate from P1).
4. **Birth count:** Filter births `obs.arrivals` units (case qty), not always `units_per_lot`.

## Consequences

- Supersedes `init_filter_bank_yields_nonempty_ordering_belief` test intent.
- VOI CRN warm-start from empty bank; may shift early rollout orders — rebaseline if needed.
- Breaking studio change: `starting_inv` field deleted.
