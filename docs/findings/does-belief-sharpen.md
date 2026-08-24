---
title: Does belief actually sharpen?
sources:
  adr: [144]
  code:
    - crates/voi_core/src/session.rs
    - crates/voi_core/src/policy.rs
    - crates/voi_core/tests/t150_phase2_arrival_model.rs
    - notebooks/13_filter_accuracy_knowledge_ladder.ipynb
    - experiments/data/nb13_channel_rows.json
    - .team/reports/T-150-arrival-remodel.md
---

# Does belief actually sharpen as you climb the ladder?

The [knowledge ladder](/ladder/rungs) is only interesting if richer observation channels
actually produce a more accurate belief about shelf freshness — otherwise it's just extra
plumbing. This page reports a direct measurement of that: replay the same 30 days of
deliveries and customer demand through six different observation rungs and see how far
each rung's belief drifts from the truth the simulator actually generated.

![Mean absolute error between believed and true shelf freshness, one bar per rung, from books-only down to a full temperature trace](/figures/rungs-accuracy-ladder.png)

## The idea

Run the store for 30 days under a fixed policy, with the *same* sequence of truck
deliveries, customer demand, and orders shared across every rung — only the store's
knowledge channel changes from run to run. Each day, compare the filter's believed mean
shelf freshness against the true mean freshness the simulator generated (which the filter
never gets to see directly). Average that gap over the month and over three random
seeds, and you get one number per rung: how far off, on average, that rung's belief runs
from the truth.

Two questions this answers directly: does adding information ever make the belief *worse*
(it shouldn't, but a modeling bug could produce that), and where on the ladder does most
of the improvement actually happen (evenly spread across rungs, or concentrated in one
step)?

## The math

For rung $r$, seed $s$, and day $t$, let $\hat f_{r,s,t}$ be the filter's believed mean
shelf freshness and $f_{r,s,t}$ the true mean shelf freshness that day. The reported
number per rung is

$$
\mathrm{MAE}(r) = \frac{1}{|S| \cdot T} \sum_{s \in S} \sum_{t=1}^{T} \left| \hat f_{r,s,t} - f_{r,s,t} \right|,
$$

with $T = 30$ days and $S = \{42, 7, 99\}$ three seeds, all replayed against the same
day-by-day sequence of deliveries and orders under the damped survival-weighted policy
(no rollout — $n_{\text{rollout\_paths}} = 0$).

Measured values (mean $|\hat f - f|$ on shelf freshness, averaged over the three seeds):

| Rung | What it observes about the delivery | MAE |
| --- | --- | --- |
| **P0** — books only | nothing | 0.109 |
| **P1** — shrink gun | nothing (waste totals only, no delivery signal) | 0.114 |
| **F2a** — pack date on the ASN | calendar duration $d$ | 0.034 |
| **F2** — lot ID + pack date | calendar duration $d$ | 0.032 |
| **F3** — + temperature history | cumulative exposure $\Lambda$ | 0.017 |

The step from a books-only rung to a pack-date rung is roughly a **3× reduction** in error
($0.109 / 0.032 \approx 3.4\times$). The further step from pack date to a full temperature
trace is smaller — about **half of the error that was still left after pack date**
($0.032 \to 0.017$ removes roughly half of that remaining 0.032) — and it is not a second
pack-date-sized jump. That smaller gain is concentrated in de-rounding the pack date (a
date is a whole calendar day; the true duration isn't) and in the residual heat-path
detail a date alone can't reveal.

## Why it's modelled this way

The measurement is designed so that the *only* thing changing between rungs is what the
filter is allowed to see — same truck deliveries, same customer demand, same order
sequence, same random seeds, replayed once per rung. ADR 0144 frames this as the
project's actual falsifier for the arrival remodel: it withdrew an earlier, purely
algebraic ordering guard (which "would pass on `sigma_T = 3.6` just as happily as on
`sigma_T = 0.4` ... it would test arithmetic, report as a model guard, and supply exactly
the false confidence that let this defect through") in favor of an *empirical* tracking
test — `crates/voi_core/tests/t150_phase2_arrival_model.rs::ac2_11a_empirical_ladder_tracking_mae`
— that asserts $\mathrm{MAE}(F3) < \mathrm{MAE}(F2) < \mathrm{MAE}(P0)$ strictly, on
simulated data, and can actually fail if the ladder ever goes flat again.

**Alternative rejected:** treating the residual-spread gap between rungs (e.g. requiring
$\mathrm{sd}(f \mid F3) < \mathrm{sd}(f \mid F2)$ at a tight tolerance) as the guard. ADR
0144 explicitly rejects this — the F2→F3 gap in residual spread is small by construction
(temperature contributes only ≈1.6% of the variance a pack date leaves unresolved; see
[Why a pack date does so much](./why-pack-date)), so a tight spread-based tolerance would
be measuring noise, not a real defect. Tracking MAE against ground truth separates the
rungs cleanly where spread comparisons don't.

**Honest caveat.** This is one 30-day trajectory family (fixed demand and delivery
schedule) replayed across three seeds — not a sweep over demand regimes, corridor mixes,
or store sizes. The Rust regression test that encodes this ordering uses a single seed and
a larger lot size (64+ units per delivery) specifically because the ordering doesn't
reliably resolve at small lot counts — at 8 units per delivery the noise floor swamps the
P0→F2 signal. The numbers above are the report's cross-seed average from the notebook
that generated them; treat the third decimal digit as noise, not signal.

## In the code

| Concept | Symbol / field | File:line |
| --- | --- | --- |
| Rung selector on a running session | `EngineSession::set_obs_scenario(&str)` | `crates/voi_core/src/session.rs:815` |
| Damped survival-weighted order from belief | `damped_sw_order_f_belief(...)` | `crates/voi_core/src/policy.rs:201` |
| Empirical ladder-ordering regression (Rust, single trajectory) | `ac2_11a_empirical_ladder_tracking_mae` | `crates/voi_core/tests/t150_phase2_arrival_model.rs:824` (assertions around line 831: `F3 < F2 < P0` strictly, `MAE(P0) ≥ 3·MAE(F2)`) |
| 30-day / 3-seed cross-rung replay (source of the table above) | `N_DAYS = 30`, `SEEDS = (42, 7, 99)` | `notebooks/13_filter_accuracy_knowledge_ladder.ipynb` |
| Per-seed, per-rung MAE rows (raw data behind the averages above) | `mae_f` column | `experiments/data/nb13_channel_rows.json` |
| Narrative summary of this finding | — | `.team/reports/T-150-arrival-remodel.md` |

## Caveats

- **Waste totals alone are not reliably more accurate than books-only on this path.** P1
  (0.114) is not better than P0 (0.109) here — if anything, slightly worse, well within
  noise. P1 adds a daily waste count but no delivery-side signal, and the arrival-freshness
  belief this page measures is driven by delivery-history channels, not POS/waste
  channels; a daily waste total mostly helps the filter reconcile counts, not the shape of
  freshness. Do not read this page as "any extra data helps" — it plainly doesn't, here.
- **Lot-code rungs without a pack date compile to the same observation bundle as P0/P1
  for this purpose.** F1 and F1s add lot-resolved POS/waste codes but still no delivery
  date or temperature trace, so their arrival-freshness belief is statistically
  indistinguishable from P0/P1's — the freshness-relevant signal lives entirely in the
  `delivery_history` channel (none / pack date / temperature history), not in the POS
  code-type or waste-granularity switches. See [The seven named rungs](/ladder/rungs) for
  why F1 and F1s are themselves identical in the current code.
- This page measures belief accuracy only. It says nothing about whether a sharper belief
  translates into better ordering decisions or more profit — that question is separate,
  and the answer is less encouraging; see [Does the money follow?](./does-money-follow)
- The measurement compares believed vs. true *shelf* freshness (a store-wide summary), not
  per-unit accuracy or the full shape of the belief distribution — two beliefs with the
  same mean error can differ a lot in how well they capture the spread.
