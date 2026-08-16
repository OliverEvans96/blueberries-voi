# Timing study — arrival-only count filter tip

**Date:** 2026-08-13  
**Status:** Measured (streams A + B)  
**Tip timed:** `team/T-069/implement` @ `6b76c5fb82dffdd780a520fa66df9cf29afac34d`  
**Worktree / branch:** `.worktrees/timing-study` on `team/timing-study` (branched from that tip)  
**Verify:** `.team/qa/T-069.md` STATUS PASS (absorbed on this tip)  
**Filter settle:** ADR [0105](../adr/0105-arrival-only-age-counts-only-exact-wor.md) + [0106](../adr/0106-shelfbelief-arrival-prior-age-exports.md)

## Tip confirmation

| Check | Result |
|-------|--------|
| SHA | `6b76c5fb82dffdd780a520fa66df9cf29afac34d` |
| ADR 0105 present | yes |
| Production ResearchParticleFilter backend | `CountsOnlyBackend` / `counts_only` |
| `mean_field_update` on `_particle_filter_update` body | **absent** (diagnostic-only in `age_likelihood`) |

## Machine knobs

| Knob | Value |
|------|-------|
| CPU | Intel Core i7-8550U @ 1.80GHz (max 4.0 GHz) |
| Logical CPUs | 8 |
| RAM | 15 GiB |
| OS | Linux 7.0.0-28-generic x86_64 |
| Python | 3.11.13 (`uv` env in worktree) |

Raw JSON artifacts (gitignored): `outputs/timing_stream_a.json`, `outputs/timing_stream_b.json`.

---

## Stream A — Offline VOI headline

### Entry points / grid

- Library: `blueberries_voi.voi` — `run_voi_crn_cell`, `run_voi_sweep`, metric + bootstrap
- Production defaults (`voi/sweep.py`): **10** betas `linspace(1,4,10)`, **7** scenarios (`P0,P1,F1,F1s,F2a,F2,B-state`), `n_rep=20`, `n_burn=30`, `n_score=60`, `filter_n=64`, `H=28`, `n_rollout_paths=8`
- Sweep structure: **200 CRN cells** = `20 reps × 10 β`; each cell runs **all 7 scenarios** under shared physics CRN

### Commands used

```bash
cd .worktrees/timing-study
uv sync --all-extras
uv run python /tmp/timing_stream_a_voi.py
# (calls run_voi_crn_cell with smoke / medium / prod-proxy budgets; writes outputs/timing_stream_a.json)
```

### Measured cells

| Cell | Budgets | Wall-clock |
|------|---------|------------|
| **Smoke** (CI-ish) | 7 scen, burn=1, score=2, N=16, H=2, paths=1 | **0.477 s**/cell (mean of 3) |
| **Medium** | 7 scen, burn=10, score=20, N=64, H=14, paths=4 | **98.7 s**/cell |
| **Prod proxy** | 1 scen (`P1`), burn=15, score=30, N=64, H=28, paths=8 | **87.9 s**/cell |

### Extrapolation (citeable headline grid)

Scale assumptions (rollout-dominated):

- From medium → prod: `(90/30 days) × ((28×8)/(14×4) H·paths) = 12×` → **~1185 s/cell**
- From proxy → prod: `×7 scenarios × (90/45 days)` → **~1231 s/cell**
- **Blended estimate: ~1208 s ≈ 20.1 min per CRN cell**

| Mode | ETA | Arithmetic |
|------|-----|------------|
| **1-box sequential** | **~67 h** (~2.8 days) | `200 × 1208 s` |
| **1-box, 8-way local fanout** | **~8.4 h** (ideal) | `67 h / 8` (no queue contention) |
| **Modal-style per-cell fanout** | **~21 min wall** | `≈ max(cell) + 30 s cold ≈ 1238 s` |

### Modal hooks

**None found** in this tip (`rg` for `modal`, `@app.function`, `modal.App` empty).

**Recommended fanout shape (not implemented):**

1. One Modal function per `(rep, beta)` CRN cell — preserves SIM-02 shared-physics CRN across scenarios inside the cell.
2. Inputs: `root_seed`, `beta`, `alpha_table_path` (or baked bytes), production budgets, shipment product id/path.
3. Output: per-scenario profits (and optional episode logs) → host aggregates bootstrap CIs / VOI metric.
4. Optional second stage: map-reduce over cells only; do **not** split scenarios across workers if CRN coupling must hold.

---

## Stream B — Pyodide / ENG-01 day latency

Native CPython proxy for the browser path. Assumed Pyodide slowdown **5×** (typical WASM range 3–10×; caveat below).

### Demo budgets (`DEMO_BUDGETS` / ADR 0099)

`n_particles=200`, `H=7`, `n_rollout_paths=2`, `candidate_case_radius=1`

### Commands used

```bash
cd .worktrees/timing-study
uv sync --all-extras
uv run python /tmp/timing_stream_b_pyodide.py
# plus act(policy='rollout') follow-up probe merged into outputs/timing_stream_b.json
```

### Timing table (native mean)

| Component | Mean | p95 | Notes |
|-----------|-----:|----:|-------|
| `day_step` alone | **0.29 ms** | 0.36 ms | physics only |
| Filter delta (`step` filter on − off) | **~84 ms** | — | arrival-only counts-only ResearchParticleFilter @ N=200 |
| Belief export (`shelf_belief_from_particle_filter_REMOVED`) | **0.08 ms** | 0.14 ms | negligible |
| `EngineSession.step(order)` | **87 ms** | 120 ms | physics + filter + export |
| Controller rollout (approx) | **~45 ms** | — | `act(rollout) − step` |
| `EngineSession.act(policy="rollout")` | **132 ms** | 202 ms | **primary interactive day** |
| `step_n` 7-day batch | 607 ms | 777 ms | ~87 ms/day |

Default `act()` without `policy="rollout"` uses constant order (~10 ms) — **not** the dialed controller demo path.

### Verdict vs &lt;1 s/day

| Metric | Value |
|--------|------:|
| Native interactive day (`act(rollout)`) | **132 ms** (~87% headroom under 1 s) |
| Assumed Pyodide (×5) | **~662 ms** (~34% headroom under 1 s) |
| **Status** | **PASS** under demo budgets with headroom at 5× |

**Knobs if margin shrinks:** lower `n_particles` (biggest filter lever), reduce `H` / `n_rollout_paths`, prefer UI-supplied orders via `step` / `step_n` when rollout is not needed every day.

---

## Top 3 bottlenecks / next actions

1. **Offline VOI nested rollout** (`H=28 × paths=8 × 90 days × 7 scenarios` per CRN cell) — drives ~20 min/cell and ~67 h 1-box. **Next:** implement Modal (or local) fanout on `(rep, β)` cells; optionally publish a “fast headline” budget ADR if citeable numbers can use smaller H/paths.
2. **Browser filter update** (counts-only ResearchParticleFilter @ N=200 ≈ 84 ms/day native) — dominates `step`. **Next:** keep N≤200 in demos; profile WOR weight loop if Pyodide factor &gt;5×.
3. **Browser controller rollout** (`H=7`, paths=2 ≈ 45 ms native on top of step). **Next:** default demo `act` to `policy="rollout"` only when UI needs it; otherwise `step`/`step_n`.

---

## Method notes / caveats

- Child stream agents returned empty; measurements re-run in this worktree on the stated tip.
- VOI headline ETAs are **extrapolations** from medium + half-horizon proxy cells, not a full 200-cell production run.
- Pyodide factor is assumed, not measured in-browser on this pass.
- Smoke shipments fixture used for VOI cells (explicit `smoke_cool_shipments`); production Abdella product I/O not in the timed path.
- Do **not** treat CI smoke VOI (`run_voi_smoke`) as the blog headline runtime.
