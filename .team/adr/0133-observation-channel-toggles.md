# 0133. Observation channel toggles replace ladder chips

STATUS: ACCEPTED
DATE: 2026-08-16
BOARD-ID: SCN-* / ENG-01 (studio)
MILESTONE: T-128 observation channel toggles
SUPERSEDES (partial UX): [0110](./0110-studio-obs-scenario-ladder.md) (six ladder chips)
RELATED: [0086](./0086-m15-richobs-unobserved-masks.md), [0123](./0123-lazy-obs-scenario-filter-caches.md),
[0124](./0124-rust-wasm-set-obs-scenario.md)

## Context

Studio exposes six ladder chips (`P0 | P1 | F1 | F1s | F2a | F2`) that map 1:1 to
`filter.types.ScenarioId`. Operators want **orthogonal** observation channels instead:
POS resolution, waste resolution, and delivery metadata are independent teaching axes.
`age_at_receipt` as a separate mask field is dropped — pack date + transit model is
sufficient (Oliver locked).

ADR 0123 lazy catch-up protocol stays: richest day log, per-configuration filter caches,
`set_obs_*` mid-episode replay. Only the cache key and UI selector change.

## Decision

### ObsChannels wire

```text
POS:        upc_only | lot_id
Waste:      none | daily_counts | lot_id
Deliveries: quantity_only | pack_date_per_lot
```

### Channel → ObsMask fields

| Always | `arrivals`, `sales_total` |
| POS `lot_id` | `sales_by_lot`, `lot_ids_live` |
| Waste `daily_counts` | `waste_total` |
| Waste `lot_id` | `waste_total`, `waste_by_lot`, `lot_ids_live` |
| Deliveries `pack_date_per_lot` | `pack_date` |

`age_at_receipt` is **not** a channel and is **not** present on any preset mask.

### Preset map (VOI backward compat)

| Preset | POS | Waste | Deliveries |
|--------|-----|-------|------------|
| P0 | upc_only | none | quantity_only |
| P1 | upc_only | daily_counts | quantity_only |
| F1 | lot_id | daily_counts | quantity_only |
| F1s | upc_only | lot_id | quantity_only |
| F2a | upc_only | daily_counts | pack_date_per_lot |
| F2 | lot_id | lot_id | pack_date_per_lot |

`ScenarioId` presets compile via `channels_for_preset` → `mask_from_channels`.
`set_obs_scenario(id)` remains a preset alias.

### Invalid combinations

All 12 orthogonal combos produce valid masks. Server rejects:

- Unknown enum values for any channel.
- `B-state` via mask APIs (unchanged).

UI **dims/disables** (not server reject):

- `f2a_transit_sd` unless `deliveries = pack_date_per_lot`.
- `sensor_sigma` unless `deliveries = pack_date_per_lot` (receipt-age teaching).
- `store-spoilage` plot unless waste ≠ `none`.

### Cache key

Lazy rung cache key = canonical string `pos=<p>|waste=<w>|deliveries=<d>` (ADR 0123).

### RPC

- Primary: `set_obs_channels({ pos, waste, deliveries })`.
- Alias: `set_obs_scenario(id)` → preset channels.
- Snapshot `applied_config` echoes `obs_channels` and matching `obs_scenario` when a preset.

## Alternatives considered

- **Keep ladder-only UX** — rejected; does not teach orthogonal channels.
- **Retain `age_at_receipt` channel** — rejected (Oliver).
- **Invalidate waste=lot_id without pos=lot_id** — rejected; F1s is valid.

## Consequences

- **Easy:** Studio toggles map directly to ADR 0086 fields; VOI presets unchanged ids.
- **Hard:** Triplicate sync (`obs.rs`, `filter/types.py`, `obsMask.ts`); UI + RPC + session cache migration.
- **Locked:** 0123 catch-up unchanged; cache keyed by channels; F2 preset uses pack_date not age.
