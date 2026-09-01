# T-163 Stage 2 (multilot) — RED criterion → test map

Recorded on `team/T-163/multilot` @ architect tip `38df6ede`. Authority:
`.team/specs/T-163.md` Stage 2 (S2.1–S2.8), `.team/qa/T-163-tests.md`, multilot plan §2–§3.

**Focused RED command:**

```bash
cargo test -p voi_core --test t163_multilot --test t_events_temp_trace --test unit_pf_ac multilot
```

## Coverage of acceptance criteria

- **S2.1 — Three lot ids** → `crates/voi_core/tests/t163_multilot.rs::delivery_mints_three_lot_ids` — currently failing: `arrival_lot_ids.len() == 1`, not 3
- **S2.2 — Exposure additivity** → `t163_multilot.rs::lot_exposure_is_upstream_plus_shared` — currently failing: events wire lacks `temp_traces_by_lot`
- **S2.3 — Per-lot splined traces** → `t163_multilot.rs::per_lot_traces_spliced` + `t_events_temp_trace.rs::events_f3_temp_trace_is_non_constant` — currently failing: no `temp_traces_by_lot` on delivery days (single pooled trace only)
- **S2.4 — Quantity split** → `t163_multilot.rs::delivery_quantity_split_not_multiplied` — currently failing: missing `arrivals_by` per-lot vector; total not split across L
- **S2.5 — LGTIN birth (three segments)** → `t163_multilot.rs::lgtin_three_segments_per_delivery` + `unit_pf_ac.rs::lgtin_multilot_delivery_segments_match_l` — currently failing: `push_lot_births` once → 1 segment, not 3
- **S2.6 — UPC mixture birth** → `t163_multilot.rs::upc_merged_cohort_uses_mixture_law` + `unit_pf_ac.rs::upc_multilot_delivery_merges_to_one_segment` — currently failing: `unit_pf.rs` does not call `sample_filter_birth_units_mixture`
- **S2.7 — Per-lot resolve** → `t163_multilot.rs::resolve_arrival_f_law_per_lot` — currently failing: single `resolve_arrival_f_law(obs)` per delivery; events lack `pack_date_days_by_lot`
- **S2.8 — FilterObs / events shape** → `t163_multilot.rs::filter_obs_carries_per_lot_pack_dates_and_traces` — currently failing: no per-lot pack dates or traces on events wire; `delivery_history_by_lot` guard passes (field absent)

## Not covered by tests

- **S2.9 — unit_ll unchanged** — because existing `n_lots` loops already suffice; verify runs full kernel regression only (no new qa test).
- **S2.10 — Full kernel suite green** — verifier gate after implement (`cargo test -p voi_core -p voi_wasm`); not part of qa RED shard.
