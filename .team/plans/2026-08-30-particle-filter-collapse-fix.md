# 2026-08-30 — LGTIN particle-filter collapse: fix, surface, guard

**Status:** COMPLETE — §3, §2 (approach b), §4 all implemented and verified; pending human merge. Branch `fix/particle-filter-collapse` in `.worktrees/pf-collapse-fix`, commits `8a8a3952` + `6f916732`. `cargo test --release -p voi_core`: 166 passed. Full `pytest` (non-slow): 746 passed, 0 regressions (4 pre-existing unrelated failures: missing rustdoc bundle, missing notebook file, studio version-bump gate). ruff + mypy clean. Regression test (`test_lgtin_high_rho_no_filter_collapse_regression`) confirmed to fail against pre-fix `unit_pf.rs` and pass against the fix. Note: the §4/§3 collapse signal was corrected from `infeasible==filter_n`/`ess<=0.0` (too sensitive — LGTIN's cross-lot likelihood genuinely goes fully infeasible on some healthy days and recovers) to "belief bit-frozen across a day with real depletion," which is what the original bug actually looked like. `act_rollout()`'s `set_obs_channels` catch-up-replay call site (session.rs ~1089) still discards filter diagnostics — left as-is per the plan's "lower priority" note.
**Read first:** `.team/handoffs/2026-08-29-lgtin-belief-accuracy-blog-post.md` and `.team/plans/2026-08-29-lgtin-belief-accuracy-blog-post.md` for the full session this bug was found during (the LGTIN `L`-truncation bug fix, the Ax rho-range widening, the resulting production run). This doc assumes that context but restates the essentials below so it can be worked independently.

---

## 0. What's broken, in one paragraph

`notebooks/damped_sw_controller_tuning.ipynb`'s Ax retune picked `rho=1.5938` (near the new `[0.5, 2.0]` ceiling). Plugging that into `article_figures.ipynb`'s production run (30 seeds × 12-cell factorial), LGTIN-coded channels intermittently collapse: the particle filter's belief freezes completely — bit-identical `lot_counts`/`f_marginals` — for the rest of the episode, while the real shelf sells down to zero and stays there. The controller, reading a frozen belief that still claims ~130 units of effective inventory, orders zero forever. Confirmed on 3+ independent (seed, channel) pairs, 100% deterministic/reproducible (not RNG noise — same inputs reproduce bit-identically every time). Root cause is in `crates/voi_core/src/unit_pf.rs`; UPC channels never trigger it because they have no cross-lot allocation step. Full day-by-day trace and evidence are in this session's transcript; the mechanism is restated precisely in §1.

**Why the Ax retune never caught this:** it doesn't use the particle filter at all. `alpha_tune.rs:319-320` calls `truth_f_belief(&freshness, &lot_offsets, ORACLE_K)` every day, for every arm including `Sw` — the oracle/ground-truth freshness readout, not any LGTIN/UPC-observed belief. The retune answers "best `(alpha,rho)` under perfect information," which is a different question than "best `(alpha,rho)` given what the store can actually observe." It has zero exposure to belief noise, bias, or collapse by construction. Worth fixing eventually (see §5, out of scope for this doc) but not blocking on it — the three items below (§2-4) fix the actual bug regardless of what the tuner does.

---

## 1. Root cause, exact

`crates/voi_core/src/unit_pf.rs`, inside `filter_step_unit_with_birth_cached` (defined ~line 534):

- Lines ~558-582: for each particle `p`, resolve the day's evidence (`DayEvidence::resolve`, gives `ev.sales_tot`/`ev.waste_tot`), propose an aging outcome, and **only if the aging proposal's likelihood `ll` is finite**, call `score_and_remove_sales(...)` to actually remove the day's sold/wasted units from that particle's tracked freshness row. If `ll` is non-finite (proposal judged infeasible — e.g. `apply_pb_aging_proposal`'s death-set didn't match `w_obs`, or `alive < sales_tot` inside `score_and_remove_sales` itself), **that particle's row is left untouched** — it keeps units it should have lost. `log_like[p]` is then set to `-1e300`.
- Lines ~584-612: weights are computed from `log_like`. If **every** particle came back infeasible, `z` (the weight sum) is `0.0`, and the code's own diagnostics say so explicitly: `StepDiagnostics { ess: 0.0, log_evidence: -inf, infeasible: n }` (line ~606-611, `n` = particle count, i.e. literally all of them).
- Line 614: `systematic_resample(&log_w)` runs **unconditionally**, even in the `z=0` case. When every particle has identical (degenerate) `log_w`, this just reshuffles the *unchanged* particles among themselves — no error, no fallback, no signal to the caller. The belief silently keeps its pre-update content.
- This is why the trace shows an *exact* freeze: not slow drift, not noise — every particle failed to deplete on the same day, so nothing in the bank changed, and (since the trigger condition — a large multi-lot mixture whose real depletion pattern is implausible under the static cross-lot allocation approximation used to score `ll`) doesn't go away, it fails again the next day, forever.
- `crates/voi_core/src/session.rs:600-610` (`advance_one`) calls `filter_step_unit_with_birth_cached(...)` and **discards the returned `StepDiagnostics` entirely** — doesn't even bind it to a variable. There is currently no path from this diagnostic to Python, Studio, or any log. (Second call site: `act_rollout()`, ~line 1072 — same pattern, lower priority since it's not on the main `article_figures.ipynb` path, but should get the same treatment for consistency — see §3.)

Why LGTIN specifically: the likelihood being scored is the static-Multinomial cross-lot allocation approximation (already flagged as LGTIN's known weak point in the earlier bug hunt, see the handoff doc §2 "Secondary, lower-confidence mechanism"). It has to explain sales across several distinct, differently-aged lots at once. A large delivery landing on an already-multi-lot bank (more likely at `rho=1.594` than `rho=0.8`, since higher rho means bigger single catch-up orders) is exactly the stress condition where that approximation's error is largest. UPC pools everything into one cohort — trivially always "explains" the day's sales, so it structurally can't hit this.

---

## 2. Fix #1 — stop the silent freeze (highest priority)

**Goal:** when the filter can't resolve a plausible per-lot depletion split, don't leave the belief's *unit count* wrong indefinitely. The day's aggregate `sales_total`/`waste_total` are always known exactly (observed regardless of `code_type` — LGTIN/UPC uncertainty is only about *which* lot each sale came from, never *how many* units sold). Losing lot attribution for one bad day is recoverable; losing the total count forever is not.

**Design (two framings — pick one, see recommendation):**

- **(a) Narrow patch — fallback only on total collapse.** In the `z <= 0.0` branch (~line 606-612), before/instead of the unconditional resample, force every particle to shed `ev.sales_tot + ev.waste_tot` units directly — bypass the likelihood-gated proposal for that day only, using a simple deterministic rule for *which* units go (e.g. remove waste from the stalest units first, sales split proportional to each lot's current live count — doesn't need to be the "correct" inference, just needs to keep the total right). Reset `log_like`/weights to uniform afterward so resampling doesn't compound the error. Smallest diff, lowest risk, directly targets the observed failure.
- **(b) General fix — decouple "does this particle survive resampling" from "does this particle apply the day's known depletion."** Currently both are gated on the same `ll.is_finite()` check, which conflates two different things: soft likelihood-based particle *scoring* (fine for it to fail per-particle) and hard depletion *bookkeeping* (should never be allowed to fail — the totals are known, not inferred). Make `score_and_remove_sales`-equivalent unconditional (always remove the known totals, using the particle's own proposal for lot attribution even when that proposal scores poorly), and let `ll` only influence resampling *weights*, not whether depletion happens at all. This fixes the root design flaw rather than special-casing the `z=0` edge — a scenario where, say, 90% of particles fail (not literally 100%) would currently still silently under-correct via biased resampling toward the 10% survivors; this framing fixes that case too, not just total collapse.

**Recommendation:** (b) is more correct and probably not much more code, but touches the core per-particle loop rather than an edge-case branch, so it deserves its own careful test pass before landing. If time-constrained, ship (a) first (it directly fixes the observed bug and is easy to reason about in isolation), then evaluate whether (b) is worth a follow-up. Either way, needs a decision on the "which units get removed" heuristic — this doesn't need to be exact (the whole point is it's a fallback for when the precise mechanism failed), but should be documented as a deliberate, simple choice, not left implicit.

**Files:** `crates/voi_core/src/unit_pf.rs` (the fix itself, ~line 540-616); check `apply_pb_aging_proposal`, `pb_sample_deaths_by_lot`, `score_and_remove_sales` (likely in `unit_ll.rs` — not yet read in detail, next agent should check before designing the exact removal call) for the right function to reuse or adapt.

**Tests:** at minimum, a regression test that reproduces tonight's exact collapse (see §4) and asserts the belief no longer diverges from truth — that on-hand *count* stays within some sane bound of real depletion even when lot attribution is uncertain. Also re-run existing `unit_pf.rs`/`session.rs` filter tests to confirm no behavior change on the non-collapse path.

---

## 3. Fix #2 — surface filter health to the caller

**Goal:** make degraded/collapsed belief *visible* instead of silently consumed, independent of whether §2 is also done — this is cheap, low-risk, and is what lets you *prove* §2 worked (count collapse-days before/after).

**Steps:**

1. `crates/voi_core/src/session.rs:600-610` (`advance_one`) — bind the currently-discarded return value: `let diag = filter_step_unit_with_birth_cached(...)`. Same at the `act_rollout()` call site (~line 1072).
2. Add a field to carry it through `DayDelta` (struct at `session.rs:1518-1529`). Something like `pub filter_diag: Option<FilterDiagValue>` (only `Some` when the filter actually ran that day — i.e. `enable_filter` true and not `BeliefSource::Truth`; `None`/omitted otherwise, including every day in the Ax-tuner's oracle path so that consumer code can't accidentally treat oracle runs as "healthy filter" runs).
3. Construct it at `session.rs:617-626` where `DayDelta` is built.
4. Serialize it in `day_delta_value` (`session.rs:711-731`) — add a top-level key, e.g. `"filter_health": {"ess": ..., "log_evidence": ..., "infeasible": ...}` (or `null`/omitted per the `Option` above). This is the dict Python's `EngineSession.act()`/`.step()` return (confirmed via `_coerce_day_delta` in `src/blueberries_voi/simulator/session.py:341`).
5. Check `src/blueberries_voi/simulator/schema.py` (`validate_day_delta`, ~line 237) — it validates the wire contract and may reject unrecognized keys or need an explicit allow-list update. `DayDelta` on the Python side is just `dict[str, Any]` (`belief.py:13`), so no dataclass changes needed there, but the schema validator needs checking.
6. Decide the Python-facing consumer story: at minimum, `channel_joint.run_seed_channel_joint` (`src/blueberries_voi/experiments/channel_joint.py`) could accumulate a per-episode collapse count/flag alongside `mae_f`/`freshness_w1` in its output row, so any downstream analysis (including `article_figures.ipynb`) can see it without re-deriving from symptoms. Not strictly required for this fix to be "done," but is the natural next consumer and worth scoping now so §4's test can assert against something real.

**Files:** `crates/voi_core/src/session.rs` (struct + call sites + serialization), `src/blueberries_voi/simulator/schema.py` (wire contract), optionally `src/blueberries_voi/experiments/channel_joint.py` (consumer).

**Tests:** a Rust unit test asserting `filter_diag` is present and matches the underlying `StepDiagnostics` on a normal day; a Python test asserting the new key round-trips through `EngineSession.act()` and passes schema validation.

---

## 4. Fix #3 — regression test that catches this class of bug

**Goal:** a test that would have failed before §2's fix and passes after, so this can't silently regress.

**Design:** construct (or reuse) a scenario that reliably stresses the multi-lot LGTIN cross-lot allocation — several distinct lots alive simultaneously with materially different freshness, followed by a demanding sales/waste sequence. Two viable approaches:

- **Deterministic repro (fastest to write):** the exact failing case from tonight is fully reproducible — seed `1784690067`, channel `{code_type: "lgtin", scan_waste: true, delivery_history: "none"}`, `alpha=0.7437600021964654, rho=1.5938240528614713`, `n_burn=7, n_score=45`, via `run_seed_channel_joint` (or the equivalent direct `EngineSession` calls — see the session transcript for the exact trace script). Turn this into a fixed-seed regression test asserting no collapse occurs (via the new `filter_health`/`ess` signal from §3) post-fix. Cheapest, but only proves this one instance is fixed, not the general class.
- **Property-based / multi-seed sweep (more robust):** generate many seeds × the LGTIN-heavy corner of the factorial (scan_waste on, any delivery_history) at a rho known to stress the system (e.g. sweep `rho` up toward `2.0`), assert `ess` never bottoms out / `infeasible` never hits the full particle count, across all of them. Catches the general class, not just the one seed. More expensive to run in CI if added to the default suite — consider gating it behind a slower/nightly test tier rather than the default `cargo test` path.

**Recommendation:** write the deterministic repro first (cheap, directly documents the bug that was found), then decide whether the sweep is worth the CI time budget — probably yes as a slower/opt-in test given how easy this was to trigger at production scale.

**Files:** likely `crates/voi_core/src/unit_pf.rs`'s existing `#[cfg(test)] mod tests` (if the fix lives there and a Rust-level repro is feasible without going through the full `EngineSession`/Python plumbing), or a new Python-level test near `src/blueberries_voi/experiments/channel_joint.py`'s existing tests if reproducing via the full session is easier. Next agent should check which layer makes the fixed seed easiest to reproduce exactly — the trace in this session used the full Python `EngineSession` path, not a minimal Rust unit test, so translating to a pure-Rust repro (faster, no Python/PyO3 build dependency) may take a bit of extra work to reconstruct the same seed/RNG-stream conditions.

---

## 5. Explicitly out of scope for this doc (tracked for later)

- Making the Ax retune belief-aware (evaluate against real LGTIN/UPC channels instead of oracle truth) — this is a separate, larger change to `alpha_tune.rs`/`damped_sw_soo.py`'s evaluation objective. Doesn't fix the underlying bug, just prevents the tuner from unknowingly picking a fragile `rho` again. Discussed in this session as "Category C" of the broader brainstorm; worth its own plan doc if pursued.
- Swapping in `sequential_kernel_path_logprob` as the real cross-lot allocation scorer instead of the static-Multinomial approximation (the "actually correct" fix vs. this doc's "detect and recover" fix). Bigger lift, likely more expensive per-step; this doc's fixes are a safety net that should stay valuable even if that lands later.
- Risk-adjusted Ax objective (mean − λ·variance) — orthogonal, doesn't require any of the above.

## 6. Suggested execution order

Despite being asked for as "1, 5, 6" (this doc's §2/§3/§4), recommend implementing **§3 before §2**: you want the `ess`/`infeasible` signal available *before* writing the fix, so you can watch it during development and confirm the fix actually eliminates collapse rather than just eyeballing profit/stockout numbers again. Then §4 (regression test) naturally follows both, since it wants to assert against the new signal. Net order: §3 → §2 → §4.
