# T-163 Phase 3 — Notebook pipeline review

**Date:** 2026-08-27  
**Branch:** `team/T-163/notebook-pipeline`  
**Base:** `team/arrival-breaks/integrate`  
**Latest commit (nb17/nb19 factorial):** `41e9b0d0`

---

## Scope completed

| Item | Status | Notes |
|------|--------|-------|
| Split nb12 → SOO + MOO | **done** | `12_damped_sw_alpha_bayesian_optimization.ipynb`, `12_damped_sw_moo_bayesian_optimization.ipynb`; rollout prose removed |
| damped_sw SOO (Modal BO) | **done** | `damped_sw_soo.py`, Modal dispatch wired; params flow to nb17/nb19 |
| nb17 channel ladder | **executed** | Modal batch; figure `figures/nb17/nb17_profit_by_package.png` |
| nb19 factorial (belief vs profit) | **executed** | 36 rows (12 cells × 3 seeds); updated `figures/channel_joint/*_mae_f.png` |
| nb19 build-your-own | **in flight** | nbconvert started ~09:29; still running at handoff (~11+ min elapsed) |

---

## Visual QA (3c)

### `figures/nb17/nb17_profit_by_package.png`

- **Pass.** Two-panel layout renders cleanly; axes labeled; no empty subplots.
- Left: mean profit ~470–485 and stockout ~20–25 across seven data packages (14 scored days, 4 seeds).
- Right: seed-paired bars show variance (seed 42 highest, seed 7 lowest) but package ordering stable within seed.
- **Surprise:** “Waste scans + pack date” slightly beats “Perfect information (ceiling)” on mean profit — likely seed noise or ceiling not truly dominating under damped_sw closed loop.

### `figures/channel_joint/` (nb19, MAE mean f)

| Figure | Verdict | Notes |
|--------|---------|-------|
| `channel_factorial_heatmap_mae_f.png` | **Pass** | Clear 2×2×3 factorial; colorbar 0.05–0.12 |
| `parallel_coords_mae_f.png` | **Pass** | 36 paths; delivery axis uses 0/1/2 ordinal |
| `profit_vs_mae_f.png` | **Pass** | Delivery types color-coded; no missing points |

- No broken/empty plots in committed PNGs.
- Legacy `*_mae_dist.png` files unchanged (still from prior run); nb19 refresh wrote `*_mae_f.png` only.

### Notebook cell outputs

- `17_prelim_channel_ladder.ipynb` and `19_channel_factorial_belief_vs_profit.ipynb`: no error/traceback outputs after execute.

---

## Analysis (3d)

### nb19 factorial (`experiments/data/nb19_joint_rows.json`)

- **36 rows**, seeds `{7, 42, 99}` only (reduced vs earlier 6-seed audit artifact — faster Modal batch for pipeline validation).
- **Delivery history dominates belief accuracy for GSIN:** `delivery=none` → mean MAE(mean f) ≈ **0.104**; with `pack_date` or `temperature_history` → ≈ **0.061–0.065**. UPC without delivery stays low (~0.057).
- **Profit weakly coupled to MAE(mean f):** scatter shows high-profit points at both low and high error; `delivery=none` GSIN runs span MAE 0.087–0.119 with profit 1020–1305 on same code/waste settings — seed-driven.
- **Waste scan toggle ≈ no effect on MAE or profit** in this factorial (on/off pairs identical to 0.001 in means) — consistent with belief channel not using waste scans in these presets.
- **GSIN vs UPC profit nearly identical** when averaged (~1130) despite large GSIN MAE penalty without delivery — closed-loop controller compensates.

### Inconsistencies / open questions

1. **S1.8 ladder ordering gap** (Phase 2 eval): MAE(P0)/MAE(F2) ≈ 1.07 vs required ≥ 3.0 — unchanged by notebook work; not in Phase 3 scope but affects interpretation of “ladder” notebooks.
2. **nb19 seed count:** 3 seeds vs nb17’s 4 — intentional for speed or oversight? Consider aligning before PR if user wants parity.
3. **Profit vs belief accuracy decoupling:** nb19 scatter suggests optimizing data channels for filter MAE may not monotonically improve damped_sw profit — worth user confirmation on narrative for blog.
4. **nb17 ceiling vs pack-date:** ceiling not strictly dominating — confirm whether ceiling preset is wired with same controller params as other packages.
5. **`nb19_run_audit.json` removed:** stale Modal shard audit from prior 6-seed run; notebook now writes `nb19_joint_rows.json` only.
6. **nb19_build_your_own_controller.ipynb:** execution pending — may produce additional figures under `figures/channel_joint/` or `.data/`; hold PR until complete or explicitly defer.

---

## Runtime notes

- nb17 + nb19 factorial: Modal batch path (`50ff65c7`); wall time dominated by remote workers (local execute ~minutes for nb19 after Modal return).
- nb19_build_your_own: nbconvert with 7200s timeout; log at `outputs/nb19_execute.log` (gitignored).

---

## PR readiness (3e)

**Deferred.** `nb19_build_your_own_controller.ipynb` still executing; no duplicate PR on `team/T-163/notebook-pipeline`. Open when build notebook finishes and optional second commit lands figures/executed notebook.

Suggested PR checklist when ready:

- [ ] nb19_build executed + figures committed
- [ ] Confirm 3 vs 6 seeds for nb19 with user
- [ ] nb12 SOO/MOO notebooks executed or note as “params only” if Modal results live outside repo
- [ ] Phase 2 S1.8 gap called out in PR body (out of scope)
