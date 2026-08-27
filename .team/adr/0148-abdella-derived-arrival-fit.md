# 0148. Abdella derived arrival product (fit like FreshNet)

STATUS: ACCEPTED — item 1's transit-temperature-moments fit and item 2's `temp_floor_c` knob SUPERSEDED BY 0150 (T-163: truncated-normal temp fit **retired**; duration gamma moment match **stays**); rest of this ADR unaffected
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
   (requires `[data]`/`[viz]`), fits corridor duration gammas, writes `arrival_model.json`,
   `fit_report.md`, overlay PNG, and `calibration_note.md`. **T-163 / ADR 0150 amendment:**
   truncated-normal transit temperature moments are no longer fitted; trip modes, hourly OU,
   and break parameters are assumed with provenance (see
   `.team/plans/arrival-transit-generative-v2.md` §3).
2. **Adjustment knobs (not refit by default):** `gamma_shape`, `gamma_scale`,
   `reference_life_days`, `q10`, `T_ref`, and `sigma_pos` (literature / MOD continuity) —
   documented in `fit_report.md` like FreshNet `demand_vm`. `temp_floor_c` is retired with
   the truncated-normal sub-model.
3. **Runtime:** Rust `include_str!` + `draw_truth_delivery`; Python filter priors sample the
   committed JSON (`arrival_model_profile.py`). **No parquet** on production defaults
   (`mod21_demo_shipments`).
4. **Supersedes** hand-authored provenance for the artifact and ADR 0043 bootstrap for filter code
   (bootstrap remains valid only in explicit diagnostic notebooks).

## Consequences

- Regenerating `arrival_model.json` may shift VOI / tuned-alpha physics epoch — regen when
  material.
- n=6 honesty remains: fit automates moments, does not validate families.
