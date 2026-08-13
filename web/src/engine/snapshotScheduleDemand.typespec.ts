/**
 * T-085 RED: type-level contract for Snapshot schedule + demand_summary.
 *
 * This module is compile-only (`tsc --noEmit` / `pnpm build`). It fails until
 * ``engine/types`` exports ``ScheduleWire`` / ``DemandSummary`` (or aliases) and
 * ``Snapshot`` includes optional ``schedule`` + ``demand_summary``.
 */
import type {
  DemandSummary,
  ScheduleWire,
  Snapshot,
} from "./types";

const schedule: ScheduleWire = {
  delivery_weekdays: [0, 2, 4],
  order_weekdays: [6, 1, 3],
  lead_time_days: 1,
  epoch: "2024-01-01",
};

const demand_summary: DemandSummary = {
  scale_mu: 30,
  dow_means: [29.1, 30.3, 27.9, 25.8, 27.8, 33.9, 35.3],
};

export const T085_TYPESPEC_SNAPSHOT: Snapshot = {
  seq: 0,
  episode_day: 0,
  belief: {
    L: 0,
    K: 1,
    lot_counts: [],
    age_marginals: [],
    tau_grid: [0],
  },
  schedule,
  demand_summary,
};

void T085_TYPESPEC_SNAPSHOT;
