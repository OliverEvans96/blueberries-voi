# Simulator export goldens (T-045 / ADR 0098)

Frozen JSON examples of the Python → host wire contract:

| File | Payload |
|------|---------|
| `snapshot_seed42.json` | Cold `EngineSession.init` **Snapshot** |
| `day_delta_seed42_step0.json` | First `step(16)` **DayDelta** after that init |
| `step_n_seed42.json` | Framed `{ "deltas": [DayDelta, ...] }` from `step_n([0, 16, 0])` |

## Generation recipe (RBPF-on)

- **Filter:** RBPF-on (`enable_filter=True`) under ADR 0099 / `DEMO_BUDGETS`
  (`n_particles=200`, `H=7`, `n_rollout_paths=2`, `candidate_case_radius=1`).
- **Shelf:** `L=2`, `K=4` (flat `age_marginals` length `L*K=8`).
- **Seed:** `42`
- **Shipments:** two in-memory `ShipmentTrace` values (no parquet / Abdella FS).
- **Order:** first delta uses `order_qty=16`; `step_n` uses `[0, 16, 0]`.

Oracle-filter goldens were not needed — RBPF-on under demo budgets is stable enough
for schema/shape contract tests (exact live byte equality is optional per T-045).

## Contract reminders

Payloads must **not** include presentation keys owned by JS: `economics`,
`pnl_series`, `pnl_totals`, `ghost`, `ghost_deltas`, `heatmap`, nested `density`,
or `ViewModel` / `view_model`.

### CAL-C1 schedule + demand summary (T-085)

Cold **Snapshot** also documents:

| Key | Role |
|-----|------|
| `schedule` | `delivery_weekdays`, `order_weekdays`, `lead_time_days`, `epoch` (`2024-01-01`) so Studio can label weekdays without redefining OrderSchedule math |
| `demand_summary` | Chart-ready `scale_mu` + length-7 `dow_means` (not the full FreshNet `demand_profile.json` blob) |

Schema helpers: `blueberries_voi.simulator.schema.validate_snapshot` /
`validate_day_delta` (T-045; reused by T-051). Must still reject forbidden
presentation keys after these fields land.
