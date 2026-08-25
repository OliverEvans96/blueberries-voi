---
title: Does belief actually sharpen?
sources:
  code:
    - crates/voi_core/src/session.rs
    - crates/voi_core/src/policy.rs
    - crates/voi_core/tests/t150_phase2_arrival_model.rs
    - notebooks/13_filter_accuracy_knowledge_ladder.ipynb
    - experiments/data/nb13_channel_rows.json
---

# Does belief actually sharpen as you climb the ladder?

The [knowledge ladder](/ladder/observation-scenarios) only matters if richer observation
channels actually produce a more accurate belief about shelf freshness. This page
measures that directly: replay the same 30 days of deliveries and customer demand through
six observation scenarios and see how far each scenario's belief drifts from the truth
the simulator generated.

![Mean absolute error between believed and true shelf freshness, one bar per observation scenario, from books-only down to a full temperature trace](/figures/scenarios-accuracy-ladder.png)

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

Measured values (mean $|\hat f - f|$ on shelf freshness, averaged over the three seeds):

| Observation scenario | What it observes about the delivery | MAE |
| --- | --- | --- |
| **Books only** | nothing | 0.109 |
| **Shrink gun** | nothing (waste totals only, no delivery signal) | 0.114 |
| **Pack date on the ASN** | calendar duration $d$ | 0.034 |
| **Lot ID + pack date** | calendar duration $d$ | 0.032 |
| **Lot ID + pack date + temperature history** | cumulative exposure $\Lambda$ | 0.017 |

The step from the books-only scenario to a pack-date scenario is roughly a **3× reduction** in error
($0.109 / 0.032 \approx 3.4\times$). The further step from pack date to a full temperature
trace is smaller — it removes roughly half of the error still left after pack date
($0.032 \to 0.017$) — and is not a second pack-date-sized jump. That smaller gain comes
from de-rounding the pack date (a date is a whole calendar day; the true duration isn't)
and from residual heat-path detail a date alone can't reveal.

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
truth avoids that gap.

**Alternative considered:** using the residual-spread gap between scenarios (e.g.
requiring the full temperature-history scenario's belief spread to be tighter than the
pack-date scenario's, at a tight tolerance) as the guard instead. The gap in residual
spread between those two scenarios is small by construction — temperature contributes
only about 1.6% of the variance a pack date leaves unresolved (see
[Why a pack date does so much](./why-pack-date)) — so a tight spread-based tolerance
would mostly measure noise, not a real defect. Tracking MAE against ground truth
separates the scenarios more cleanly.

**Honest caveat.** This is one 30-day trajectory family (fixed demand and delivery
schedule) replayed across three seeds — not a sweep over demand regimes, corridor mixes,
or store sizes. The Rust regression test that encodes this ordering uses a single seed
and a larger lot size (64+ units per delivery) because the ordering doesn't reliably
resolve at small lot counts — at 8 units per delivery the noise floor swamps the signal
between the books-only and pack-date scenarios. The numbers above are the cross-seed
average from the notebook that generated them; treat the third decimal digit as noise,
not signal.

## In the code

| Concept | Symbol / field | File:line |
| --- | --- | --- |
| Observation-scenario selector on a running session | `EngineSession::set_obs_scenario(&str)` | `crates/voi_core/src/session.rs:815` |
| Damped survival-weighted order from belief | `damped_sw_order_f_belief(...)` | `crates/voi_core/src/policy.rs:201` |
| Empirical ladder-ordering regression (Rust, single trajectory) | `ac2_11a_empirical_ladder_tracking_mae` | `crates/voi_core/tests/t150_phase2_arrival_model.rs:824` (assertions around line 831: `F3 < F2 < P0` strictly, `MAE(P0) ≥ 3·MAE(F2)`) |
| 30-day / 3-seed cross-scenario replay (source of the table above) | `N_DAYS = 30`, `SEEDS = (42, 7, 99)` | `notebooks/13_filter_accuracy_knowledge_ladder.ipynb` |
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
- This page measures belief accuracy only. It says nothing about whether a sharper belief
  translates into better ordering decisions or more profit — that question is separate,
  and the current answer is less encouraging; see
  [Does the money follow?](./does-money-follow)
- The measurement compares believed vs. true *shelf* freshness (a store-wide summary), not
  per-unit accuracy or the full shape of the belief distribution — two beliefs with the
  same mean error can differ a lot in how well they capture the spread.
