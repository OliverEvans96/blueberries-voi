# 2026-08-30 — Full session recap: LGTIN figures, particle-filter collapse, per-channel tuning, Studio integration

**Branch:** `fix/lgtin-l-dim-truncation` (PR #88, off `main`)
**Companion docs:** `.team/handoffs/2026-08-29-lgtin-belief-accuracy-blog-post.md` (the earlier L-truncation bug hunt this session continues from) and `.team/plans/2026-08-29-lgtin-belief-accuracy-blog-post.md` / `.team/plans/2026-08-30-particle-filter-collapse-fix.md` (decision logs for their respective arcs). This doc is the overarching narrative tying the whole night together, with heavier detail on everything from the "why did the nice result disappear" investigation onward, which isn't fully captured elsewhere.
**Purpose:** Oliver is writing a blog post about the blueberries-voi VOI/POMDP model. This session covers building the post's figures, finding and fixing a real particle-filter bug along the way, an extended investigation into why a promising early result didn't reproduce at production scale, and wiring the resulting per-channel controller tuning into Blueberry Studio.

---

## 1. Where the night started

Continuing from `.team/handoffs/2026-08-29-...md`: a `belief_flat_from_unit_bank` wire-truncation bug (`L`-dim) had just been found and fixed (`DEFAULT_L_DIM` 10→50), restoring LGTIN's expected "at least as informative as UPC" behavior. `notebooks/article_figures.ipynb` existed as the reproducible source for every post figure, initially run locally at 8 seeds. The immediate next steps queued up were: widen the `rho` search range, retune the shared `damped_sw` controller via Ax, and re-run the article figures at production scale.

## 2. Rho range widened; first production run; independent audit requested then cancelled

Widened `RHO_BOUNDS` from `(0.5, 1.0)` to `(0.5, 2.0)` in both the Studio slider (`web/src/controls.ts`) and notebook 12's Ax search space, restructured notebook 12 into 4 batches of 12 trials (48 total, `AX_PARALLELISM=4`) so a manual run could be stopped early, and moved `article_figures.ipynb` to a 30-seed Modal production run. Rewrote the notebook's Modal dispatch to match notebook 12's own established pattern (self-built `uv_sync` image, explicit-argument shard functions) rather than the older `experiments/modal/app.py` pattern, per Oliver's request for consistency.

Oliver then asked for an independent sonnet-subagent audit of both notebooks before running anything for real. That audit was launched, then **cancelled mid-run** at Oliver's request so the plan/handoff docs could be brought current first — the audit had been working from a stale version of the plan. Docs were updated (`.team/plans/2026-08-29-...md` §2.6) and a fresh, thorough audit prompt was drafted but never actually launched, because the very next thing that happened made an audit moot: Oliver ran the notebooks himself and reported the results looked much worse than a run he'd liked earlier.

## 3. The "what happened" investigation — the largest single arc of the night

Oliver: *"the latest notebook run is much worse... I don't like that the least-informative regimes are the highest-profit... it seems like a red flag"* and later flagged that the "no delivery history" combination scored highest in the full factorial scatter — backwards from what the belief-accuracy story predicted.

### 3.1 Initial (wrong) diagnosis, then walked back

First hypothesis: `alpha=0.9999` (pinned exactly at the search boundary, from a *second* retune done under narrower `rho <= 1.0` bounds) looked like a degenerate optimum. Oliver pushed back with real data: an earlier run at `alpha=0.744, rho=1.594` (interior, not boundary-pinned, from the *first* retune under `rho <= 2.0` bounds) showed the same flat profit ladder. That ruled out boundary-pinning as the cause and was an important correction — I'd been too quick to blame the most visually suspicious number.

### 3.2 Systematic isolation testing

Built a self-contained local test harness (bypassing Modal, calling `EngineSession` directly) to reproduce the original good 8-seed ladder and then vary one parameter at a time against it: `alpha`/`rho`, `K` (freshness bins), `n_burn`/`n_score`, `arrival_product`, `obs_scenario`. Each systematically ruled out:
- **The particle-filter collapse fix itself** (see §4) — reverting the Rust crate entirely to pre-fix and re-testing gave byte-identical results to both post-fix framings, at the gentle `(alpha=0.95, rho=0.8)` operating point. Confirmed the fix genuinely has zero effect there.
- **K, arrival_product, obs_scenario** — matched exactly, no effect.
- **The actual culprit, found by finally checking the original notebook cell instead of trusting memory:** the original good run used `N_BURN, N_SCORE = 2, 30` — a much shorter episode than the `14, 45` used throughout the "production" reruns, which had never been verified against the source. Reverting to `2, 30` alone restored a strong monotonic ladder (up to +3.9%).
- **But `filter_n` also mattered independently:** the original run used the notebook pipeline's thin `filter_n=24` default, not Studio's real `filter_n=200`. At `filter_n=200`, even the short `2/30` episode with the good `(0.95, 0.8)` tuning went flat again.

### 3.3 Mechanistic explanation

The clean monotonic result was substantially a **cold-start recovery effect**: a short, thinly-warmed-up episode is dominated by how fast a better-informed channel restocks from empty, which is a real but narrow phenomenon. Over a longer, more realistic episode at a realistic particle count, the system spends most of its time at steady state, where the profit differentiation from information is small and, under this specific cost regime (cheap waste, expensive stockout, `DEFAULT_STORE_ECONOMICS` — never independently calibrated), sometimes slightly negative. Belief accuracy (W1) stayed robustly, cleanly monotonic through every single configuration tested — this was the one bulletproof finding of the whole night.

Oliver's explicit framing throughout, which shaped everything downstream: *"I think a profit-maximizing controller is appropriate — we don't want to artificially tune the controller to support our hypothesis that belief helps profit."* Findings were reported as findings, not massaged toward a nicer story.

## 4. The particle-filter collapse bug

While investigating, found (with help from a background subagent earlier, and directly here) that LGTIN's belief could freeze bit-for-bit across days with real depletion, because `filter_step_unit_with_birth_cached` (`crates/voi_core/src/unit_pf.rs`) gated a particle's sales/waste removal on that particle's likelihood being finite — when *every* particle failed on the same day (a real, measured ~12.78% of days for LGTIN at `filter_n=24`, vs. 0.83% for UPC), nothing got removed and the belief silently kept its stale count while the real shelf depleted toward zero, causing the controller to stop reordering entirely.

**Two fix framings were discussed and empirically compared, not just reasoned about:**
- **(a)** Narrow: only force unconditional depletion on literal total collapse (every particle fails); otherwise behave exactly like pre-fix code (gated on feasibility, pruned by resampling).
- **(b)** General (what had been committed by another process before I revisited it): unconditional depletion every day for every particle, regardless of individual feasibility.

Direct A/B measurement (not just code review) showed both framings produce byte-identical results on the production `(alpha, rho)` — the broader unconditional behavior bought nothing beyond collapse prevention that the narrower gate didn't already provide. **Oliver chose (a)**, the smaller-surface-area fix. Implemented, validated against `cargo test -p voi_core` and the full Python suite including a deterministic regression test reproducing the exact original collapse, committed (`8726230f`).

Measured `filter_n=200`'s effect on the collapse rate directly (Oliver's request, after I'd initially only theorized about it): total-collapse dropped from 12.78% to 3.33% — a real, meaningful reduction, but far short of the near-zero a naive per-particle-IID model would predict. That gap is evidence of a persistent "hard core" of days where the static-Multinomial cross-lot allocation approximation assigns the true outcome near-zero density regardless of particle count — a case for eventually swapping in the exact `sequential_kernel_path_logprob` scorer, not just relying on more particles.

## 5. Production regeneration at the real, honest parameters

Re-ran `article_figures.ipynb` at `filter_n=200` (Studio's real default, not the notebook's thinner 24), `n_burn=2, n_score=30`, and the non-boundary-pinned `(alpha=0.744, rho=1.594)` shared retune. Committed (`8e231396`). Result: belief accuracy cleanly monotonic (down to 0.204 ratio at Temp history); profit flat (0.985–1.007), consistent with everything in §3 — the honest answer, not a bug.

## 6. Per-channel tuning — the textbook-correct VOI measurement, tried twice

Oliver had floated tuning each of the 12 factorial channels independently rather than one shared policy: *"whatever information you have, you tune the best profit-maximizing controller you can... that seems justifiable."* Discussed why this matters: the existing Ax retune scores against `truth_f_belief` (oracle/ground-truth), never any real channel's belief — confirmed by tracing `alpha_tune.rs`. A shared oracle-tuned policy has no reason to transfer safely to what a specific channel's real, imperfect belief looks like. Per-channel tuning (`V*(info) = max_policy E[profit | info]` per information set) is the textbook-correct way to measure value-of-information; the shared-policy approach is a simplification that trades rigor for cost.

### 6.1 First attempt — K_BO_SEEDS=4, overfitting

Added a new per-channel tuning section to notebook 12 (12 channels tuned concurrently via `ThreadPoolExecutor`, each with its own Modal-dispatching Ax loop, genuine `run_seed_channel_joint` belief at `filter_n=200`). Hit and fixed a real bug on the first run: the new Modal image never mounted `/experiments`, so a fallback path inside `profit_session_config` crashed trying to read `tuned_alpha.json` even though its result was unused. Fixed, re-ran successfully.

Results looked great at first glance: a clean monotonic ladder recovered in profit, and the "backwards" delivery-history pattern fixed. **This didn't survive scrutiny.** Comparing each channel's tuning-time profit (scored on only 4 seeds during Ax optimization) against its true profit on `article_figures.ipynb`'s independent 30-seed evaluation showed every channel inflated, and — critically — the inflation was *larger for information-richer channels* (+58 for `upc|off|none` vs. +137 for `lgtin|off|temperature_history`). Classic BO overfitting to an under-sampled objective, not a real effect. Committed honestly as a finding, not a fix (`ad119ddb`).

### 6.2 Discussed and ruled out: common random numbers (CRN)

Before re-tuning, discussed whether CRN across channels/candidates was the missing piece. It wasn't — both were already correctly implemented (a single fixed `PC_BO_SEEDS` list shared across every trial and every channel). The overfitting was a sample-size problem (SEM of each trial's own profit estimate), not a comparison-fairness problem CRN would address.

### 6.3 Second attempt — K_BO_SEEDS=30, properly validated

Oliver: *"please re-run with 30 tuning seeds."* Also requested 50 trials/channel with max Modal parallelism (clarified through a couple of corrections down to: keep `AX_PARALLELISM=4`, don't bother enforcing an artificial concurrency cap since none was actually wired up). Estimated wall-time (~20–45 min) and cost (~$0.35–0.80, CPU-dominated) from Modal's stated pricing before running. Cancelled partway through when Oliver reported Modal's account-level 100-concurrent-container cap; re-estimated wall-time under that constraint (~15–30 min realistic range from first principles); then, on Oliver's instruction, cancelled the 50-trial run and restarted at **25 trials/channel** instead (9,000 total shard evaluations).

Result: the overfitting gap shrank to small and nearly uniform across channels (+32.7 to +46.4, SD 4.0 — generic optimizer's-curse bias, not differentiated overfitting), confirming the methodology fix worked. But the underlying profit story still isn't a clean win: held-out ladder ratios all ≥ 1.0 (better than the flat/negative shared-policy runs) but not monotonic and not distinguishable from noise (differences of a few dollars against per-rung SD ~100+). Delivery-history factorial breakdown remains backwards. Committed (`c0c5f06f`) with an honest writeup, not a declared fix.

**Bottom line after exhausting shared vs. per-channel policy, multiple episode lengths, and multiple particle counts:** belief accuracy is robust and monotonic everywhere. Profit is not, anywhere realistic. That consistency across such a wide sweep is itself evidence this is the real finding, not an artifact waiting on one more parameter tweak.

## 7. New figure: per-channel optimal (alpha, rho) scatter

Oliver asked for a figure mirroring the existing belief-vs-profit factorial scatter, but plotting each channel's own tuned `(alpha, rho)` instead (initially typed "row" for "rho" — confirmed from context). Added, same legend grammar (color=waste, marker=delivery, size=code type), with dashed reference lines at the Ax search bounds. Visually confirms the finding: all 12 channels cluster tightly (`alpha` 0.65–0.88, `rho` 1.25–1.65), nowhere near the bounds, no visible separation by information richness. Committed (`e06a0ed9`).

## 8. Studio integration

Oliver asked Studio to use the per-channel tuned values by default and whenever observation channels change, and separately confirmed the data needs to be **fully accessible in the deployed cross-repo build** (blueberries-voi → personal-website via the `@oliverevans96/blueberries-voi-studio` npm tarball, `release-studio.yml`, `repository-dispatch` to `OliverEvans96/personal-website`).

- New `web/src/perChannelTuning.ts`: the 12-cell tuning table embedded as a TS constant (not a fetched JSON asset) — Vite bundles it directly into `dist-lib/embed.js`, sidestepping any risk from `copy-lib-assets.mjs` only handling fonts/CSS, not arbitrary data.
- `DEFAULT_CONTROLLER_CONTROLS` (`controls.ts`) now starts at the tuned pair for Studio's real default channels (`upc|on|none`), not the old hardcoded boundary-pinned shared value.
- `applyObsSelection` (`studioLogic.ts`) re-syncs `alpha`/`rho` to the new channel's own tuning on every channel change.
- Verified three ways, not just by reading the diff: `tsc --noEmit` clean; live in the browser across two real channel switches (values matched the tuning file exactly); and by actually running `npm run build:lib` (the release workflow's own command) and grepping the tuned values out of the built `dist-lib/embed.js`.
- Fixed a real, pre-existing-but-now-triggered test: `studioWiring.test.ts` did a raw 1200-character source-slice-and-regex check on `applyObsSelection` that my added code pushed past; widened to 2500 rather than trimming the comment to fit an arbitrary window. Committed (`a20bdc0e`).
- Follow-up: updated the `rho` slider's tooltip, which still described it as a "fraction... closed each order day" — only sensible for `rho <= 1`. Since the range now goes to 2.0, rewrote to describe it accurately as a multiplier that can overshoot the target above 1. Slider min/max (`0.5`/`2`) had already been widened earlier in the session. Committed (`7963d9d6`).
- Version bump: Oliver asked about bumping the minor version, then said patch-level (already at `1.0.8` vs. `main`'s `1.0.1`) was fine — no minor bump made.

## 9. Recurring git/process hygiene notes

- **Concurrent session interference continued to be real**, as flagged in the prior handoff. Mid-session, an external process (author `Oliver Evans`, same identity used for all commits) renamed `notebooks/12_damped_sw_alpha_bayesian_optimization.ipynb` → `notebooks/damped_sw_controller_tuning.ipynb` as part of a broader repo-wide numeric-prefix cleanup, deleted one superseded notebook, and archived another — all outside this session's own commits. Verified content survived the rename intact before fixing this session's own stale references to the old filename (`f88314e5`). Another external commit (`update notebook outputs`) landed between two of this session's commits without incident.
- A stale **staged-but-uncommitted** change to `session.rs` (reverting the `filter_health` diagnostics surfacing) was found sitting in the git index from earlier in the session, unrelated to the working tree (which was already correct). Unstaged before committing rather than accidentally including it.
- `outputs/` and `notebooks/outputs/article_figures/` are gitignored but contain files already tracked from earlier in the session — new files in those directories need `git add -f`.
- GPG commit signing is off for this session (`--no-gpg-sign`, explicitly authorized earlier) since interactive pinentry doesn't work in this environment.

## 10. Current state / what's genuinely still open

- **The article's central empirical question is answered, but not resolved in the direction originally hoped for.** Belief accuracy: robust, large, monotonic, publishable as-is. Profit: flat-to-noise under every honest configuration tried. Four framing options were laid out for Oliver to choose among (not decided yet): (1) lead with belief accuracy, treat profit as a secondary, carefully-caveated result; (2) invest further in de-noising per-channel tuning beyond 25 trials/30 seeds; (3) reconsider whether `DEFAULT_STORE_ECONOMICS` (never independently calibrated) is a representative cost regime, on its own merits, not to manufacture a result; (4) let the null result itself be part of the article's narrative.
- The blog draft (`/home/oliver/job-search/afresh-blog-post/my-post/2026-08-26 Draft.md`) has **not** been updated to reflect any of tonight's work — still describes pre-fix results and an old controller framing. Explicitly out of scope tonight; flagged as still pending in earlier task tracking (rewriting the controller paragraph, swapping in final figures/numbers, adding the gamma-process figure).
- `sequential_kernel_path_logprob` (the exact cross-lot scorer) remains unused — the real fix for the residual LGTIN collapse rate, not yet undertaken.
- No further audit has been run since the one cancelled in §2; given how much has changed since, a fresh audit (if still wanted) would need to be scoped against this doc, not the earlier one.

## 11. Key files touched tonight (beyond §1's carryover)

- `crates/voi_core/src/unit_pf.rs` — the collapse fix (framing a).
- `notebooks/damped_sw_controller_tuning.ipynb` (renamed from `12_damped_sw_alpha_bayesian_optimization.ipynb`) — shared retune (unchanged structurally) + new per-channel tuning section.
- `notebooks/article_figures.ipynb` — filter_n=200, `n_burn=2/n_score=30`, per-channel controller consumption, new alpha-vs-rho scatter.
- `outputs/damped_sw_alpha_bo_per_channel.json` — the final (K=30, 25 trials) per-channel tuning result.
- `web/src/perChannelTuning.ts`, `web/src/controls.ts`, `web/src/react/studioLogic.ts` — Studio integration.
- `.team/plans/2026-08-30-particle-filter-collapse-fix.md` — the detailed technical plan/status for the collapse fix specifically (§0-§4 there cover the bug and fix options in more depth than this recap does).
