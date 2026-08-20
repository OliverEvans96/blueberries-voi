# 0135. Wire pre-sampled arrival freshness through session, VOI, and F2 filter birth

STATUS: ACCEPTED
DATE: 2026-08-20
TICKET: T-134
RELATED: [0130](./0130-f-native-c2-a-unit-pf.md), [0131](./0131-f-native-wire-tau-retirement.md),
MOD-11 / MOD-21 (Abdella arrival mix)

## Context

C2-A production paths (`session.rs`, `voi.rs`) call `arrival_receipt_meta` to populate
`RichDay.f_at_receipt` / `age_at_receipt` for the observation mask, then invoke `unit_day_step`
with `delivery_f: None`. Inside `unit_day_step`, birth freshness is re-sampled via
`delivery_birth_f` and independent shipment RNG streams. Rollout forward simulation already
fixes this by passing the pre-drawn `(f_at_receipt, age_at_receipt, pack_date_days)` tuple.

Symptoms: truth `live_lots[].mean_f` at delivery can disagree with the arrival prior chart;
F2 filter particles ignore observed `age_at_receipt` because `birth_f` never reads that field;
changing `arrival_product` in studio has no effect on WASM physics when shipments are not sent
on the wire.

## Decision

1. **Single birth draw:** Session and VOI pass the receipt tuple into `UnitDayStepIn` exactly
   like `rollout.rs`; omit shipment RNG when `delivery_f` is `Some`.
2. **Embedded MOD-21 demos:** Add `mod21_demo_shipments` + `truth_birth_from_trace` in
   `shipments.rs` (constant 1 °C traces calibrated to teaching ages at `q10=3`, `t_ref=0`).
3. **RPC hydration:** When configure/init lacks explicit shipment arrays, resolve
   `arrival_product` → demo trace set (default `abdella_all`).
4. **F2 filter:** `unit_pf::birth_f` honors `FilterObs.age_at_receipt` via `birth_f_f2_dirac`.

## Alternatives rejected

- **Re-sample in day_step only for session:** Still wastes RNG and breaks CRN alignment with
  filter obs on the same day.
- **Ship full parquet in WASM bundle:** Too heavy; demo traces suffice for studio teaching mix.
- **Web sends shipment JSON on every init:** Duplicates MOD-21 logic already needed in Rust for
  VOI/offline paths.

## Consequences

- Truth inventory freshness at receipt matches logged metadata and arrival-prior charts.
- F2 scenario filter birth aligns with observed receipt age.
- Studio `arrival_product` chips affect WASM physics without manual shipment arrays.
- Tests must guard against regressing to `delivery_f: None` in session/voi.
