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
channels actually produce a sharper belief about shelf freshness — not just a more
complicated one. This page checks that directly. We replay the same 30 days of truck
deliveries and customer demand through the five-rung observation ladder — books only,
+ scan waste, + pack date, + LGTIN, + temperature history — and measure how far each
scenario's belief drifts from the truth the simulator generated.

+LGTIN refers to a barcode that combines a product's Global Trade Item Number (GTIN)
with a batch/lot number, so it identifies the specific delivery batch a unit came from,
not just the product line — different from a shipment-level identifier.

## The idea

Run the store for 30 days under a fixed ordering policy, with the *same* sequence of
truck deliveries, customer demand, and orders shared across every scenario — only the
store's knowledge channel changes from run to run. This is an open-loop replay: because
every scenario plays out against identical, pre-generated ground truth, any difference
in belief accuracy can only come from what's observed, not from luck in the random draws.

Each day, we compare the filter's believed freshness distribution against the true
freshness distribution the simulator generated (which the filter never sees directly).
We summarize that day's gap with the 1-Wasserstein distance (W1) — a measure of how far
apart two distributions are — then average over the month and over 30 random seeds to
get one number per scenario, reported below as a ratio to the books-only baseline.

Two questions this answers: does adding information ever make the belief *worse* (it
shouldn't, but a modeling bug could produce that), and where on the ladder does most of
the improvement happen — spread evenly, or concentrated in one step?

Two modeling details are worth knowing before reading the results. First, cold-chain
breaks generate real, randomly varying thermal exposure along each truck's route, rather
than a single averaged temperature draw, so the temperature-history scenario has genuine
thermal information to resolve rather than a rounding error. Second, each delivery is
modeled as three separate lots rather than one, so lot identity can distinguish units
that arrived on the same calendar day but rode in different trucks or sat in different
positions — this is what lets the LGTIN scenario add information beyond the pack date
alone.

## The math

For observation scenario $r$ and day $t$, let $B_{r,t}$ be the filter's believed
distribution over shelf freshness and $G_t$ be the simulator's true freshness
distribution that day — the same $G_t$ for every scenario, since every scenario replays
against identical ground truth. Comparing full distributions, rather than just their
averages, matters because two beliefs can share the same mean freshness while
disagreeing sharply about the spread.

We use the 1-Wasserstein distance (W1) between $B_{r,t}$ and $G_t$, averaged over
$T = 30$ days and 30 random seeds, then expressed as a ratio to the books-only baseline:

$$
\text{Belief W1 ratio}(r) = \frac{\text{average } W_1(B_{r,\cdot}, G_\cdot) \text{ over days and seeds}}{\text{average } W_1(B_{\text{books only},\cdot}, G_\cdot) \text{ over days and seeds}}
$$

A ratio below 1 means scenario $r$'s belief sits closer to the truth than books-only; a
ratio above 1 means it's farther off. Every scenario replays against the same day-by-day
sequence of deliveries and orders, under the same ordering policy — the survival-weighted
policy described in the In-the-code table below — so the only thing that varies is what
each scenario is allowed to see.

Measured over a 30-day replay and 30 random seeds:

| Observation scenario | What's added | Belief W1 ratio vs. books-only (95% CI) | Profit ratio vs. books-only (95% CI) |
| --- | --- | --- | --- |
| Books only | Deliveries and sales counts — what nearly every store already tracks | 1.000 (baseline) | 1.000 (baseline) |
| + scan waste | A scan of what got thrown out (waste scanning) | 1.036 ± 0.026 | 1.009 ± 0.008 |
| + pack date | The pack date from the delivery paperwork (Advance Ship Notice, or ASN) | 0.453 ± 0.048 | 1.003 ± 0.015 |
| + LGTIN | The lot-level barcode, tying units to their specific delivery batch | 0.301 ± 0.019 | 1.004 ± 0.014 |
| + temp. history | A logged temperature record for that batch's trip | 0.214 ± 0.013 | 1.006 ± 0.014 |

The profit-ratio column comes from a separate closed-loop replay of the same scenarios
and seeds, where each scenario's controller is actually allowed to place orders. It's
included here for context — see [Does the money follow?](./does-money-follow) for the
full story.

**Belief accuracy improves steadily as you move down the ladder, and pack date is the
single biggest jump.** Adding pack date cuts belief error by more than half — the ratio
drops from 1.000 to 0.453, a little over 2× sharper than books-only. Scanning spoiled
units alone doesn't help: its ratio (1.036 ± 0.026) is statistically indistinguishable
from, or slightly worse than, books-only. Adding the LGTIN barcode sharpens things
further (0.301), and adding temperature history sharpens them again (0.214) — roughly
4.7× sharper than books-only overall.

**Profit, meanwhile, stays essentially flat.** Every scenario lands within about 1% of
the books-only baseline. A sharper belief about freshness doesn't translate into more
profit in this experiment — that's a settled result, not noise or an open question. The
likely reason is that the ordering policy is short-sighted: it optimizes over only the
next few days of demand and current mean freshness, not the berries' full shelf life of
roughly ten days, so it can't fully exploit a sharper belief. See
[Does the money follow?](./does-money-follow) for the full breakdown, including why the
cost assumptions — a missed sale costs roughly 4.3× as much as a wasted unit once you
count both the stockout penalty and the forgone margin — already push this policy close
to profit-optimal even with a coarse belief.

## Why it's modelled this way

The measurement is designed so the only thing changing between scenarios is what the
filter is allowed to see: the same truck deliveries, the same customer demand, the same
order sequence, and the same random seeds are replayed once per scenario. A regression
test in the codebase checks this ordering empirically against the simulator's actual
ground truth — it confirms that error decreases monotonically as scenarios get richer,
from books-only down through temperature history, and fails if the ladder ever goes
flat. A check that only verifies arithmetic relationships between input parameters,
without touching simulated ground truth, wouldn't catch a real modeling defect;
comparing against ground truth closes that gap. (See the In-the-code table below for the
exact test.)

An alternative was considered: comparing the spread of each scenario's belief directly,
instead of its distance from ground truth. That's a reasonable design too, but distance
from truth separates the scenarios more cleanly — especially now that temperature breaks
generate genuinely variable thermal exposure rather than a single averaged number, which
would make a spread-based check mostly measure that added variability rather than
whether the belief is actually more accurate.

**Honest caveat.** This is one 30-day trajectory family — fixed demand and delivery
schedule — replayed across 30 seeds, not a sweep over demand regimes, shipping-route
profiles, or store sizes. The codebase's automated regression test that encodes this
ordering uses a single seed and a larger lot size than the store default (64+ units per
delivery, versus 8 in the results above), because the ordering doesn't reliably resolve
at small lot counts: at 8 units per delivery, random noise swamps the signal between
books-only and pack-date.

## In the code

| Concept | Symbol / field | File:line |
| --- | --- | --- |
| Observation-scenario selector on a running session | `EngineSession::set_obs_scenario(&str)` | `crates/voi_core/src/session.rs:1249` |
| Order quantity from belief (the survival-weighted policy) | `damped_sw_order_f_belief(...)` | `crates/voi_core/src/policy.rs:246` |
| Automated check that error decreases monotonically down the ladder (single trajectory) | `ac2_11a_empirical_ladder_tracking_mae` | `crates/voi_core/tests/t150_phase2_arrival_model.rs:809` (assertions at lines 879–890) |
| Replay notebook that generates ladder-comparison data | `N_DAYS = 30`, `SEEDS = (42, 7, 99)` | `experiments/modal/app.py::nb13` (`src/blueberries_voi/experiments/filter_accuracy.py`) |
| Per-seed, per-scenario error rows (raw data behind notebook averages) | `mae_f` column | `experiments/data/nb13_channel_rows.json` |

## Caveats

- **Waste totals alone are not reliably more accurate than books-only on this path.**
  Scanning spoiled units (1.036 ± 0.026) is not better than books-only (1.000) here — if
  anything, slightly worse, and close to the noise floor. Waste scanning adds a daily
  waste count but no delivery-side signal, and the arrival-freshness belief this page
  measures is driven by delivery-history channels, not point-of-sale (POS) or waste
  channels; a daily waste total mostly helps the filter reconcile counts, not the shape
  of freshness. Don't read this page as "any extra data helps" — it plainly doesn't,
  here.
- **Lot-code scenarios without a pack date behave the same as books-only for this
  purpose.** The observation grid has a few additional presets beyond the five-rung
  ladder above — for example, a lot-ID preset with no delivery history at all, and a
  full-knowledge "oracle" preset — which are useful extra detail for readers who want the
  full 12-combination grid at [the observation scenarios page](/ladder/observation-scenarios).
  Adding a lot-resolved barcode at the point of sale or on the waste scan, with no
  delivery date or temperature trace behind it, doesn't change the arrival-freshness
  belief at all: the freshness-relevant signal lives entirely in what's known about the
  delivery (none, pack date, or temperature history), not in the code type or the waste
  scan.
- This page measures belief accuracy only. It says nothing on its own about whether a
  sharper belief translates into better ordering decisions or more profit — see
  [Does the money follow?](./does-money-follow) for that question and the full
  explanation of the flat-profit result above.
- The table above already reports the shape-aware $W_1$ distance rather than a plain
  mean error, because two beliefs can share the same average freshness while differing a
  lot in spread. Continuous Ranked Probability Score (CRPS) — one clause: how well a full
  predictive distribution, not just its mean, matches what actually happened — is used
  elsewhere in the project when scoring the particle filter's predictions for on-hand
  unit counts. The interactive studio's belief-accuracy table reports both a mean-error
  view and a $W_1$ view side by side; see [The studio, guided](/using-it/studio-guide).
