# 0148. Abdella derived arrival product (fit like FreshNet)

STATUS: ACCEPTED — item 1's transit-temperature-moments fit and item 2's `temp_floor_c` knob SUPERSEDED BY 0150; rest of this ADR unaffected
DATE: 2026-08-25
GROUP: MOD
RELATED: [0115](./0115-freshnet-derived-demand-product.md), [0144](./0144-f-native-hierarchical-arrival-model.md),
[0150](./0150-arrival-thermal-break-events.md)

## Context

ADR 0144 committed a hierarchical arrival law in `arrival_model.json`, but parameters were
**hand-authored** with a reporting-only overlay script. Python filter paths still **bootstrapped**
six parquet traces. Oliver requested Abdella follow the FreshNet pattern: **offline fit →
committed JSON + fit_report**, parametric runtime, explicit **adjustment knobs**.

## Decision

1. **Offline fit only:** `scripts/fit_abdella_arrival.py` reads vendored `data/abdella/*.parquet`
   (requires `[data]`/`[viz]`), fits corridor duration gammas and truncated-normal transit
   temperature moments, writes `arrival_model.json`, `fit_report.md`, overlay PNG, and
   `calibration_note.md`.
2. **Adjustment knobs (not refit by default):** `gamma_shape`, `gamma_scale`,
   `reference_life_days`, `q10`, `T_ref`, `temp_floor_c`, and `sigma_pos` (literature /
   MOD continuity) — documented in `fit_report.md` like FreshNet `demand_vm`.
3. **Runtime:** Rust `include_str!` + `draw_truth_delivery`; Python filter priors sample the
   committed JSON (`arrival_model_profile.py`). **No parquet** on production defaults
   (`mod21_demo_shipments`).
4. **Supersedes** hand-authored provenance for the artifact and ADR 0043 bootstrap for filter code
   (bootstrap remains valid only in explicit diagnostic notebooks).

## Consequences

- Regenerating `arrival_model.json` may shift VOI / tuned-alpha physics epoch — regen when
  material.
- n=6 honesty remains: fit automates moments, does not validate families.
