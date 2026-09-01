# 2026-08-29/30 — Decisions log + forward plan: LGTIN belief-accuracy fix, blog post figures

Companion to `.team/handoffs/2026-08-29-lgtin-belief-accuracy-blog-post.md` (read that first for narrative context). This doc is the decision record and the concrete not-yet-executed plan.

**Status as of 2026-08-30:** everything in §1 (decisions) is done and merged into the working tree on `fix/lgtin-l-dim-truncation` (PR #88, open). §2's design has since been **finalized and committed into both notebooks** (rho bounds, Ax batch structure, article_figures seed count/Modal dispatch — see §2.6 below for the final locked-in values, which supersede the specific numbers quoted in §2.1/2.2/2.4 below). One calibration step (§2.3) was explicitly approved and run early on. **Execution of the actual production runs (Ax retune, article_figures Modal run) has NOT started** — an independent audit of both notebooks was requested before running; that audit was started, then cancelled mid-run at Oliver's request so the plan/handoff docs could be brought current first (a fresh audit prompt is being prepared separately). §2.1-§2.5 below are kept as-written for the historical reasoning; treat §2.6 as the authoritative current config.

---

## 1. Decisions made (all resolved, all applied)

| # | Decision | Rationale | Where it landed |
|---|---|---|---|
| 1 | Controller: **`damped_sw` only**, no SLA controllers in the post | `channel_joint.run_seed_channel_joint` already hardcodes `damped_sw` regardless of alpha source (discovered mid-session — prior "sla_pb" framing in conversation was a mislabel). `sla_mc` showed a real MC non-convergence bug (order jumped 16→128 units between 128→256 paths on a toy belief). `damped_sw` already matches the draft's existing controller formula, zero rewrite needed. | No code change needed — already the de facto behavior. Confirmed as the intentional choice going forward. |
| 2 | `DEFAULT_L_DIM`: 10 → **50** | Root-caused the LGTIN-looks-worse-than-UPC anomaly to `belief_flat_from_unit_bank`'s fixed-`L` wire truncation, which hits LGTIN far harder than UPC (LGTIN fragments deliveries into more lot segments). Benchmarked `L=3,10,20,30`: no runtime cost difference among 10/20/30 under `damped_sw` or `sla_pb` (well inside 500ms/1000ms Studio budgets); `sla_pb` tail latency was worse at `L=3`. Chose 50 for headroom since the cost is effectively free. | `crates/voi_core/src/params.rs` |
| 3 | `profit_session_config`'s literal `"L": 3` override → **50** | This Python-side literal was silently overriding the Rust default for every notebook/experiment figure — fixing only the Rust constant would have changed nothing for tonight's work. | `src/blueberries_voi/experiments/voi_profit.py` |
| 4 | Add `day_w1_error` (Wasserstein-1 belief-accuracy metric) | Needed a metric that works over the full arbitrary `ObsChannels` factorial, not just nb17's 6 named Rust-binary presets, so belief accuracy and profit could be measured from the *same* pipeline/seeds. | `src/blueberries_voi/experiments/belief_accuracy.py`, wired into `channel_joint.py` |
| 5 | Belief-accuracy figures use a **shared-order replay design**, not raw closed-loop | Raw closed-loop scoring confounds filter accuracy with the controller: better-informed rungs order differently, diverging their actual truth trajectories. Replay (one truth trajectory per seed via a shared order schedule, only the observation mask varies) isolates the intended comparison. Profit figures stay closed-loop (profit is inherently a closed-loop concept). | `article_figures.ipynb`'s ladder section; same design manually reproduced for the LGTIN-specific forest-plot sketch |
| 6 | Notebook cleanup finalized | See handoff §6 for the full file list. | Committed on `fix/lgtin-l-dim-truncation` |
| 7 | GPG-sign commits: **off for this session** | Pinentry can't open a TTY in this environment; Oliver explicitly authorized `--no-gpg-sign` rather than leaving commits blocked. | Applied to all 5 commits on `fix/lgtin-l-dim-truncation` |
| 8 | Tonight's work branches off **`main`**, not `feat/arrival-lottery-studio` | The arrival-lottery-studio commit is a narrow, complete, unrelated Studio UI feature (one commit, no file overlap with anything backend/notebook). Bundling would confuse review scope for both. | New branch `fix/lgtin-l-dim-truncation`; `feat/arrival-lottery-studio` pushed/PR'd separately, untouched |
| 9 | Secondary LGTIN approximation (static-multinomial cross-lot allocation) — **documented, not fixed** | Real, understood mechanism (see handoff §2), plausibly explains the no-delivery-history residual gap, but genuinely open-ended fix (better closed-form approximation, or accept the cost of exact sequential-path scoring) — out of scope for tonight. | Flagged in PR #88 description and handoff doc; not actioned |

## 2. Forward plan (NOT YET EXECUTED — awaiting go-ahead)

### 2.1 Rho range → `[0.5, 2]` (both places)

- **Studio slider**: `web/src/controls.ts:388` — `<input type="range" id="rho" min="0.1" max="1" step="0.01" />` → `min="0.5" max="2"`. Default value (`rho: 0.8`, line 125) stays inside the new range as-is unless the Ax retune (§2.4) suggests overwriting it.
- **Ax search space**: `notebooks/12_damped_sw_alpha_bayesian_optimization.ipynb`, cell 2 — `RHO_BOUNDS = (0.5, 1.0)` → `(0.5, 2.0)`.
- Studio change needs a `scripts/build-wasm.sh` rebuild afterward (~30s) to take effect live.
- **Open question:** should the Ax retune's result overwrite `experiments/tuned_alpha.json`'s `"sw"` entry and Studio's default `rho: 0.8`, or does Oliver want to review the Ax output first?

### 2.2 Ax retune — 50 trials, Modal, "maximum concurrency"

`notebooks/12_damped_sw_alpha_bayesian_optimization.ipynb` already has a complete, working Modal-dispatched joint `(alpha, rho)` Ax BO harness — no new code needed, just config edits in cell 2:
- `TOTAL_AX_TRIALS`: 24 → **50**
- `RHO_BOUNDS`: per §2.1
- `AX_PARALLELISM` (trials proposed per Ax round, currently 4) and `MODAL_CONCURRENCY` (concurrent Modal shards, currently 32) are the concurrency knobs — each trial evaluates on `K_BO_SEEDS=6` seeds, so `AX_PARALLELISM × 6` shards fire per round. Proposed for "maximum": `AX_PARALLELISM≈10-15`, `MODAL_CONCURRENCY≈100`. **These are guesses, not known account limits** — Modal queues rather than errors on overshoot, so erring high is safe but possibly not actually faster than a lower setting if the real ceiling is lower.
- `FULL_RUN = True` already set (`n_burn=n_score=28`, four weeks) — real episode length, not smoke-sized. Leave as-is unless told otherwise.
- Output: new `outputs/damped_sw_alpha_bo.json` with retuned `(alpha, rho)`. Feeds into §2.1's open question and into §2.4.

### 2.3 Modal calibration — DONE, one data point

Oliver approved running this specific step ("perform the calibration now to inform the plan") ahead of the rest. Ran `channel_joint` via `run_batch(..., "modal", ...)`, 2 seeds × 2 channels = 4 shards, tiny episode (`n_burn=2, n_score=5`):

```
TOTAL WALL TIME: 37.8s for 4 shards
tqdm progress showed the shard-execution portion itself as ~5s once running (~1.25s/shard) —
the remaining ~33s was Modal image build/dispatch overhead (cold start), not computation.
```

**Caveat on this run:** it executed while the working tree was — unknown to us at the time — reverted to pre-fix `main` content by a concurrent checkout from the other agent session (see handoff §5). So this timing data is real and usable (compute cost doesn't meaningfully change with `L` or the presence of `day_w1_error`), but it did **not** validate the fix running on Modal. Working tree has since been restored to `fix/lgtin-l-dim-truncation` and verified correct (`DEFAULT_L_DIM=50`, `freshness_w1` present). If a validation run matters before committing to the production numbers below, redo a small Modal smoke test now that the tree is correct.

**Implication for sizing:** Modal's overhead is dominated by cold start (~30s fixed-ish), not per-shard compute. This argues for *fewer, larger* shards where possible (batch more seeds/work per Modal function invocation) rather than many tiny ones, to amortize the fixed cost — current `channel_joint` shard granularity is one `(seed, channel)` pair per invocation, which is fine but not maximally efficient for Modal specifically.

### 2.4 Production rerun of `article_figures.ipynb`

Budget given: **max 15 min wall-clock, max 1 CPU-hour Modal budget** (`app.py` functions request `cpu=1.0` each, so 1 CPU-hour = 3600 CPU-seconds total across all shards combined), max concurrency.

Sizing math, once real per-shard timing `T` (including cold start amortization) is known from a fresh §2.3-style calibration:
- Max shard count ≈ `3600 / T`
- Required concurrency to fit 15 min wall ≈ `(shard_count × T) / 900`

Proposed scope (unchanged from tonight's local-run scope, just re-dispatched to Modal with tuned values):
- Gamma-process and cold-chain-calibration figures: **no Modal needed** — pure Python math and a single Rust example invocation respectively, not batch jobs.
- Ladder replay + full-factorial + appendix sections: move to Modal dispatch (`run_batch(..., "modal", ...)` instead of `"local"`).
- Seed count: tonight's local runs used 8 seeds (~230 shard-equivalents total across the three Modal-bound sections). Conservative starting point for the production run; scale up only if calibration shows real headroom within budget.
- Controller values: the freshly Ax-tuned `(alpha, rho)` from §2.2, not tonight's ad hoc `(sw-table alpha, rho=0.8)`.

**Not yet decided:** exact final seed count (depends on §2.3 redo), whether to increase `n_score`/`n_burn` beyond tonight's 30/2 given more budget is available, and the §2.1 open question about whether tuned values become the new defaults everywhere or stay notebook-local for this run.

### 2.5 Sequencing

1. Edit rho bounds (Studio `controls.ts` + notebook 12) — no compute.
2. Rebuild wasm for Studio.
3. (Optional but recommended) redo a small Modal smoke test now that the tree is verified correct, to get trustworthy timing.
4. Ax retune, 50 trials — the long pole; duration depends on real per-trial Modal timing.
5. Resolve the §2.1 open question (overwrite defaults or not).
6. Rerun `article_figures.ipynb` with Modal dispatch + tuned values, sized from step 3's numbers, within the 15min/1CPU-hr cap.

### 2.6 FINAL locked-in config (2026-08-30) — supersedes §2.1/§2.2/§2.4 numbers above

Committed on `fix/lgtin-l-dim-truncation` in three commits (`fb3a4fa8`, `9ab759d6`, `b5e76331`). **Not yet executed** — config only.

**Studio + Ax search space (`web/src/controls.ts`, `notebooks/12_damped_sw_alpha_bayesian_optimization.ipynb`):**
- Rho range: `[0.5, 2.0]` everywhere (Studio slider, `RHO_BOUNDS`, `RHO_BOUNDS` in article_figures.ipynb for its own fallback default). `DEFAULT_RHO = 0.8` unchanged, still inside range.
- Ax retune split into **4 batches of 12 trials each (48 total)**, not one 50-trial run — reasoning per Oliver: easier to stop early on a manual run, and each batch reports progress/improvement vs. the previous batch. `run_ax_batch(batch_num, n_trials_this_batch)` helper shared by all 4 batch cells; batch 1 initializes (or reloads) the Ax client, batches 2-4 continue it.
- `AX_PARALLELISM = 4` (was a guessed 10-15 in §2.2 above — Oliver gave an explicit number instead).
- `MODAL_CONCURRENCY = 100` for the Ax retune (unchanged guess from §2.2, not re-validated against real account limits).
- `FULL_RUN = True`: `N_BURN = N_SCORE = 28`, `K_BO_SEEDS = 6`.
- Still not executed, so `outputs/damped_sw_alpha_bo.json` does not yet exist — article_figures.ipynb's controller-value cell falls back to `outputs/tuned_alpha.json`'s `"sw"` entry + `rho=0.8` until it does.

**`article_figures.ipynb` production sizing:**
- **30 seeds** (was 8): `SEEDS = tuple(int(s) for s in np.random.default_rng(2026).integers(0, 2**31 - 1, size=30))` — fixed-RNG reproducible, not hand-picked.
- `N_BURN, N_SCORE = 7, 45` (was `N_BURN=2` at smoke scale; `N_SCORE` raised from tonight's earlier local runs to 45 for tighter CIs — this is a real increase in episode length, not just seed count, so cost scales more than linearly vs. the 8-seed baseline timing in §2.3).
- Modal dispatch pattern **rewritten to match notebook 12's own established pattern exactly** (self-built `uv_sync(frozen=True)` image, explicit-argument shard functions — `_process_seed_ladder(seed, ladder, n_burn, n_score, alpha, rho)` etc. — no closures over notebook globals, chunked spawn+get via `dispatch_modal(fn, jobs, label)`), per Oliver's explicit request to keep Modal usage consistent across notebooks rather than diverging into the older `experiments/modal/app.py` pattern.
- `MODAL_CONCURRENCY = 64`, `MODAL_FUNCTION_TIMEOUT_S = 600.0` for article_figures (independent of notebook 12's Ax-retune concurrency knob above).
- Factorial section's shard calls now pass `controller_alpha=ALPHA, controller_rho=RHO` explicitly (previously relied on implicit defaults inside `run_seed_channel_joint` — a consistency fix, not a behavior change under current values).
- **Not yet executed.** Both notebooks regenerated/syntax-checked only (no cell outputs).

**Immediately outstanding before running for real:** an independent audit of both notebooks (methodology + code correctness) — requested by Oliver, one attempt started and cancelled before completion so this doc could be brought current first; see the audit prompt prepared alongside this update.

## 3. Standing risk to watch

The working directory is shared with at least one other concurrent agent session, which has twice (once early, once mid-session after being told to stop) performed unrequested `git checkout`/`git stash` operations on this exact working tree, silently reverting tracked files and once leaving HEAD detached. **Before trusting any "current state" observation in a future session, check `git branch --show-current` and `git status` are what's expected, and cross-check against `git reflog` if anything looks off**, rather than assuming local file content matches the last-known-good state.
