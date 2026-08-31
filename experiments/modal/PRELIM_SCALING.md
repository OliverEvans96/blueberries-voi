# Preliminary notebook scaling (T-157)

Durable notes for notebooks **17** and **18** Modal budgets. Current targets stay
under roughly **10 min wall** and **2 CPU-hr** per notebook on Modal CPU workers.

## Current prelim budgets (nb17 / nb18)

| Notebook | Batch jobs | Grid | Scored window | Rough CPU |
|----------|------------|------|---------------|-----------|
| **17 Part 1** (`gsin`) | 8 shards | 4 regimes × 2 seed indices | diagnostic replay (full truth week per shard) | ~8 × 30–60 s ≈ 4–8 CPU-min |
| **17 Part 2** (`voi_profit`) | 28 shards | 6 presets × 4 seeds + 4 oracle | `n_burn=2`, `n_score=14` | ~28 × 20–40 s ≈ 9–19 CPU-min |
| **18** (`rollout_eval`) | 8 shards | 4 seeds × 2 arms (sw + rollout) | `n_burn=2`, `n_score=14`, `H=7`, `paths=4` | ~8 × 60–120 s ≈ 8–16 CPU-min |
| **21** (`controller_bakeoff`) | 40 shards | 10 seeds × 4 arms (no rollout/dp/sla_mc) | `n_burn=2`, `n_score=14`, oracle SIM-01=B | ~40 × 0.02–0.05 s local; Modal similar |

**Smoke mode** (`SMOKE=True`): one gsin shard, one profit seed/channel, two scored
days; one rollout seed/arm; one channel_joint seed/channel; one controller_bakeoff
seed/arm — for plumbing only.

**Controller worlds differ:** nb17 Part 2 uses filtered beliefs per data package;
nb18 `rollout_eval` uses **oracle-shelf** (SIM-01=B) — perfect on-shelf state, not
nb17 filter outputs. nb19 `channel_joint` uses filtered beliefs in closed loop (same
physics as nb15 profit shards) but records accuracy on scored days.

## Notebook 19 (`channel_joint`)

| Target | Grid | Scored window | Rough CPU |
|--------|------|---------------|-----------|
| **19** joint shard | ~72 shards (6 seeds × 12 channels) | `n_burn=2`, planned `n_score` 10–30 | probe one shard → `plan_channel_joint_budget` under 20 min / 2 CPU-hr |

Use `experiments/modal/render_nb19_figures.py` after `nb19_joint_rows.json` lands.

## Notebook 21 (`controller_bakeoff`)

| Target | Grid | Scored window | Rough CPU |
|--------|------|---------------|-----------|
| **21** oracle bakeoff | 40 shards (10 seeds × 4 arms) | `n_burn=2`, `n_score=14` | local probe: sw ~0.03 s, sla_pb ~0.02 s per shard (2026-08) |
| **21** filtered appendix | 30 shards (10 seeds × 3 arms, no rung0) | same | `BELIEF_WORLD=filtered`, P0 channels via `session.act` |

Optional filtered appendix: set `BELIEF_WORLD=filtered` (excludes rung0).

## Medium-priority increases

When Modal ceilings rise beyond ~10 min / 2 CPU-hr per notebook:

| Upgrade | Notebook | New budget (indicative) | Rough CPU |
|---------|----------|-------------------------|-----------|
| Full gsin grid | 14-style / nb17 Part 1 | 48 cells (4 regimes × 12 seeds) | ~48 × 45 s ≈ 36 CPU-min |
| Longer profit score | nb17 Part 2 | `n_score=28–30`, 6+ seeds, optional `filter_n` sweep | ~36–48 jobs × 30 s |
| More rollout seeds / days | nb18 | 6–12 seeds, `n_score=21–28`, keep `H=7` `paths=4` | ~12–24 jobs × 90 s |
| Longer rollout horizon | nb18 only if shards stay &lt;3 min | `H=14` (not H=28 until dedicated bakeoff) | watch per-shard wall time |
| Production bakeoff | **16** (not 18) | alpha grid, `H=28`, `paths=8`, 12 seeds | notebook 16 path |

## What NOT to do blindly

- **Alpha grid in nb18** — prelim fixes α from `sw_alpha_bo.json`; sweeps belong in nb16.
- **H=28 + paths=8 in nb18** — reserved for production bakeoff; will blow the 10 min ceiling.
- **Mixing controller worlds** — do not compare nb17 filter profit to nb18 rollout deltas as if they share beliefs.
- **Lowering `n_score` below 10** only when rollout shards exceed ~3 min each; document the change here.

## Rehearsal checklist

1. Build wheel + `gsin_upc_diag` (see `experiments/modal/README.md`).
2. Run config cells locally with `BATCH_MODE="local"` or Modal with `SMOKE=True` first.
3. Log wall time and `completed/total` from `run_batch` progress lines.
4. If rollout shards exceed ~3 min, reduce `N_SCORE` to 10 and note it in this file.
