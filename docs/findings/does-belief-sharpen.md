---
title: Does belief actually sharpen?
sources:
  adr:
    - "0149"
    - "0150"
  code:
    - crates/voi_core/src/session.rs
    - crates/voi_core/src/policy.rs
    - crates/voi_core/tests/t150_phase2_arrival_model.rs
    - experiments/modal/app.py
    - experiments/data/nb13_channel_rows.json
---

# Does belief actually sharpen as you climb the ladder?

The [knowledge ladder](/ladder/observation-scenarios) only matters if richer observation
channels actually produce a more accurate belief about shelf freshness. This page
measures that directly: replay the same 30 days of deliveries and customer demand through
six observation scenarios and see how far each scenario's belief drifts from the truth
the simulator generated.

## The idea

Run the store for 30 days under a fixed policy, with the *same* sequence of truck
deliveries, customer demand, and orders shared across every scenario — only the store's
knowledge channel changes from run to run. Each day, compare the filter's believed mean
shelf freshness against the true mean freshness the simulator generated (which the filter
never sees directly). Average that gap over the month and over three random seeds, and
you get one number per scenario: how far off, on average, that scenario's belief runs
from the truth.

Two questions this answers: does adding information ever make the belief *worse* (it
shouldn't, but a modeling bug could produce that), and where on the ladder does most of
the improvement happen — spread evenly, or concentrated in one step?

**What changed (ADR 0149 / 0150).** Two modelling gaps that made middle rungs look flat
are fixed:

- **Temperature (F3):** the old trace was decorative — it matched a scalar φ̄ already
  drawn from a truncated normal, leaving ~1.6% of `Var(log Λ)` for F3 to resolve after a
  pack date. Break events inside a generative path (`truth_transit_trace` →
  `resolve_arrival_exposure`) give F3 real thermal residual to mop up; expect the **F2 → F3
  step to grow** relative to the old ladder.
- **Lot identity (GSIN):** with one lot per delivery, lot ID was redundant with shelf age
  on a M/W/F schedule (pack-date 0.034 → lot ID + pack-date 0.032). **Fixed `L = 3` lots
  per delivery** (ADR 0149) puts three same-calendar-age cohorts at **different
  freshness** on the shelf, so lot-resolved channels should **separate more** from
  pack-date-only once multi-lot wiring lands.

## The math

For observation scenario $r$, seed $s$, and day $t$, let $\hat f_{r,s,t}$ be the filter's
believed mean shelf freshness and $f_{r,s,t}$ the true mean shelf freshness that day. The
reported number per scenario is

$$
\mathrm{MAE}(r) = \frac{1}{|S| \cdot T} \sum_{s \in S} \sum_{t=1}^{T} \left| \hat f_{r,s,t} - f_{r,s,t} \right|,
$$

with $T = 30$ days and $S = \{42, 7, 99\}$ three seeds, all replayed against the same
day-by-day sequence of deliveries and orders under the damped survival-weighted policy
(no rollout — $n_{\text{rollout\_paths}} = 0$).

Measured values (mean $|\hat f - f|$ on shelf freshness, averaged over the three seeds;
**from the last notebook run before the breaks + multi-lot docs pass — re-run
`modal run experiments/modal/app.py::nb13` to refresh after integrate merges**):

| Observation scenario | What it observes about the delivery | MAE |
| --- | --- | --- |
| **Books only** | nothing | 0.109 |
| **Shrink gun** | nothing (waste totals only, no delivery signal) | 0.114 |
| **Pack date on the ASN** | calendar duration $d$ | 0.034 |
| **Lot ID + pack date** | calendar duration $d$ (+ lot-resolved birth under GSIN) | 0.032 |
| **Lot ID + pack date + temperature history** | cumulative exposure $\Lambda$ from path | 0.017 |

The step from the books-only scenario to a pack-date scenario is roughly a **3× reduction** in error
($0.109 / 0.032 \approx 3.4\times$). That ratio is still the headline pack-date win.

Under the old model the further step from pack date to a full temperature trace was a small
mop-up (~1.6% of exposure variance left after duration). With generative breaks, **F3
should close a larger gap** — de-rounding the pack date still matters, but so does resolving
break damage the date cannot see. The table numbers above pre-date a full notebook re-run on
the integrate tip; treat the **ordering** (richer scenarios beat poorer ones; pack date beats
books-only by ~3×) as stable and the **third decimal** as provisional until the notebook
is re-executed.

With **three lots per delivery**, the lot-ID + pack-date row should **pull away further**
from pack-date-only once Stage 2 wiring is live — the old 0.034 → 0.032 gap reflected lot
identity buying almost nothing over age alone.

## Why it's modelled this way

The measurement is designed so the only thing changing between scenarios is what the
filter is allowed to see — same truck deliveries, same customer demand, same order
sequence, same random seeds, replayed once per scenario. The regression test that
encodes this,
`crates/voi_core/tests/t150_phase2_arrival_model.rs::ac2_11a_empirical_ladder_tracking_mae`,
checks the ordering empirically against simulated ground truth: it asserts that MAE
strictly increases as you go from the richest scenario down to the least-informed one —
the full temperature-history scenario has the least error, then the pack-date scenario,
then the books-only scenario has the most — and fails if the ladder ever goes flat. A purely algebraic guard — one that only checks arithmetic relationships
between input parameters — would pass regardless of whether the simulated ladder actually
tracks correctly, so it wouldn't catch a real modeling defect. Testing against ground
truth avoids that gap. **`ac2_11a` remains the binding correctness gate** on the integrate
branch (`F3 < F2 < P0` strictly, `MAE(P0) ≥ 3·MAE(F2)`, `MAE(F3)` near the Bayes floor).

**Alternative considered:** using the residual-spread gap between scenarios (e.g.
requiring the full temperature-history scenario's belief spread to be tighter than the
pack-date scenario's, at a tight tolerance) as the guard instead. Under the **old**
truncated-normal model the gap in residual spread between F2 and F3 was small by
construction — temperature contributed only about 1.6% of the variance a pack date left
unresolved (see [Why a pack date does so much](./why-pack-date)). Under **break events**,
F3's residual is larger by design, so a tight spread-based tolerance would mostly measure
noise, not a defect. Tracking MAE against ground truth separates the scenarios more cleanly.

**Honest caveat.** This is one 30-day trajectory family (fixed demand and delivery
schedule) replayed across three seeds — not a sweep over demand regimes, corridor mixes,
or store sizes. The Rust regression test that encodes this ordering uses a single seed
and a larger lot size (64+ units per delivery) because the ordering doesn't reliably
resolve at small lot counts — at 8 units per delivery the noise floor swamps the signal
between the books-only and pack-date scenarios. The notebook table above is the cross-seed
average from the last run that generated it; treat the third decimal digit as noise until
the notebook is re-run on the integrate tip.

## In the code

| Concept | Symbol / field | File:line |
| --- | --- | --- |
| Observation-scenario selector on a running session | `EngineSession::set_obs_scenario(&str)` | `crates/voi_core/src/session.rs:1249` |
| Damped survival-weighted order from belief | `damped_sw_order_f_belief(...)` | `crates/voi_core/src/policy.rs:246` |
| Empirical ladder-ordering regression (Rust, single trajectory) | `ac2_11a_empirical_ladder_tracking_mae` | `crates/voi_core/tests/t150_phase2_arrival_model.rs:809` (assertions at lines 879–890: `F3 < F2 < P0` strictly, `MAE(P0) ≥ 3·MAE(F2)`) |
| 30-day / 3-seed cross-scenario replay (source of the table above) | `N_DAYS = 30`, `SEEDS = (42, 7, 99)` | `experiments/modal/app.py::nb13` (`src/blueberries_voi/experiments/filter_accuracy.py`) |
| Per-seed, per-scenario MAE rows (raw data behind the averages above) | `mae_f` column | `experiments/data/nb13_channel_rows.json` |

## Caveats

- **Waste totals alone are not reliably more accurate than books-only on this path.** The
  shrink-gun scenario (0.114) is not better than books-only (0.109) here — if anything,
  slightly worse, well within noise. The shrink-gun scenario adds a daily waste count but
  no delivery-side signal, and the arrival-freshness belief this page measures is driven
  by delivery-history channels, not POS/waste channels; a daily waste total mostly helps
  the filter reconcile counts, not the shape of freshness. Don't read this page as "any
  extra data helps" — it plainly doesn't, here.
- **Lot-code scenarios without a pack date compile to the same observation bundle as
  books-only/shrink-gun for this purpose.** The "lot ID at POS" and "lot ID on the shrink
  gun" scenarios add lot-resolved POS/waste codes but still no delivery date or
  temperature trace, so their arrival-freshness belief is statistically indistinguishable
  from the books-only/shrink-gun scenarios' — the freshness-relevant signal lives entirely
  in the `delivery_history` channel (none / pack date / temperature history), not in the
  POS code-type or waste-granularity switches. See
  [The seven named observation scenarios](/ladder/observation-scenarios) for why those two
  scenarios are themselves identical in the current code.
- **MAE table numbers are stale until the notebook re-runs** on the integrate tip with
  breaks + `L = 3`; the qualitative ladder story and `ac2_11a` ordering guard are the
  stable claims.
- This page measures belief accuracy only. It says nothing about whether a sharper belief
  translates into better ordering decisions or more profit — that question is separate,
  and the current answer is less encouraging; see
  [Does the money follow?](./does-money-follow)
- The table above still reports shelf-mean freshness **MAE** (a store-wide summary).
  That is a useful regression anchor, but it does not score the full shape of the
  freshness belief: two beliefs with the same mean error can differ a lot in spread.
  Preferred shape-aware scores elsewhere in the project are **$W_1$** (1-Wasserstein)
  between live freshness belief and truth for distribution fidelity, and **CRPS** of
  the particle predictive for on-hand count $N$ when particle samples are available.
  The interactive studio's belief-accuracy table uses mean-f MAE plus freshness $W_1$
  (All-days = mean of daily $W_1$); see [The studio, guided](/using-it/studio-guide).
  Notebook ladders may still publish MAE while those distributional metrics roll out.
