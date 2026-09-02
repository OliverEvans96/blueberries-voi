---
title: The Belief Wire
sources:
  code:
    - crates/voi_core/src/belief_flat.rs
    - crates/voi_core/src/unit_pf.rs
    - crates/voi_core/src/session.rs
---

# From particles to charts: the wire

The [particle filter's internal state](/inference/what-one-particle-is) is a bank of hundreds of complete, unit-level shelf hypotheses — one freshness number per believed-alive unit, in every particle. Nothing downstream wants to receive that directly — not a chart in Blueberry Studio (the project's interactive dashboard), not the ordering policy, not a Python or TypeScript client — because it's too much data, shaped inconveniently, and tied to Rust-internal representations. So on every step the filter's belief gets flattened onto a small, fixed-shape summary called the **belief wire** — a histogram-per-lot projection that throws away most of the particle-level detail on purpose. This page explains what that projection keeps, what it discards, and how to size it correctly.

## The idea

Picture the filter's real state as a spreadsheet: one row per particle, one column per unit currently believed alive, cell values are freshness. That's rich, but it's also an awkward shape — the number of columns changes every day as lots arrive and die, and no chart or policy function wants to read raw per-particle, per-unit numbers.

The wire compresses this into something fixed-shape and much smaller: pick `L` "lot slots" (oldest-first, the most recent `L` lots the filter is currently tracking) and `K` freshness bins spanning `[0,1]`. For each of the `L` slots, compute two things across the whole particle bank: the *expected* number of alive units in that lot (weighted by particle weight — this becomes `lot_counts`), and a *histogram* of what fraction of those alive units fall in each of the `K` freshness bins (this becomes `f_marginals`, one row of length `K` per lot, normalized to sum to 1). The bin centers themselves are `f_grid`, spaced evenly across `[0,1]`.

This is genuinely a display-and-policy artifact, not the filter's actual belief. Two particles that agree on a lot's histogram can still disagree wildly about which *specific* unit is fresh and which is nearly spoiled — that correlation structure is exactly what the wire throws away. The ordering policy reads only this flattened summary (it needs "how many effectively-fresh units do I have," not "which specific unit"), so the lossiness is a deliberate simplification for the policy's sake, not an accident of the export format.

## The math

Let the particle bank hold $N$ particles, each with a normalized weight $w^{(i)}$ — how much the filter currently trusts particle $i$'s hypothesis, with all particles' weights summing to 1 — and let the bank's own lot segmentation currently track $n_\ell$ lots (oldest-first, offsets shared across all particles — see [What one particle is](/inference/what-one-particle-is)). The wire keeps only the newest $L$ of those lots:

$$
\text{first} = \max(0,\ n_\ell - L)
$$

so wire slot $s = 0, \dots, L-1$ corresponds to filter lot $\ell = \text{first} + s$. For each wire slot $s$, spanning filter-lot units $j \in (\text{first}, \text{end}]$:

$$
\text{lot\_counts}[s] = \sum_{i=1}^N w^{(i)} \cdot \#\left\{\, j \in \text{lot } \ell : f^{(i)}_j > 0 \,\right\}
$$

which is the particle-weighted expected count of *alive* units (freshness $>0$) in that lot. For the histogram, with $K$ evenly spaced bin centers $g_0, \dots, g_{K-1} \in [0,1]$ (`f_grid`), and writing $f^{(i)}_j$ for particle $i$'s own freshness value for unit $j$:

$$
\text{f\_marginals}[s, k] \;\propto\; \sum_{i=1}^N w^{(i)} \sum_{j \in \text{lot } \ell,\ f^{(i)}_j > 0} \mathbb{1}\!\left[k = \arg\min_{k'} \left|f^{(i)}_j - g_{k'}\right|\right]
$$

normalized so $\sum_k \text{f\_marginals}[s,k] = 1$ for every slot $s$ (a slot with zero alive-unit mass exports a uniform histogram, $1/K$ in every bin, rather than dividing by zero). Note the sum only includes units with $f^{(i)}_j > 0$ — dead units never contribute to a lot's freshness histogram, only to the fact that `lot_counts` is lower than the lot's original size.

## Why it's modelled this way

**Fixed `L×K` shape, not a variable-length export.** The belief wire is a flat `L×K` buffer specifically so that Blueberry Studio's schema validators, Rust, Python, and the frontend all agree on one fixed contract regardless of how many lots or particles the filter is actually tracking internally. A second, dual wire that also carried a calendar-time-since-arrival axis alongside the freshness one was considered and rejected: two parallel meanings for "where a unit sits" would leave the studio's code, its reference test data, and the frontend charts all needing to disambiguate which one a given payload meant.

**Histogram summary, not a richer per-particle export.** A richer, higher-fidelity histogram representation was compared against the shipped design in benchmarks; its better histogram-shape fidelity didn't justify the extra cost at the shelf sizes actually used, so the coarser, cheaper `f_marginals` summary is the production default.

**`L` is a wire-sizing knob, not a filter capacity limit.** This is the detail most likely to be misunderstood, so it's worth stating precisely: the particle filter's own internal state is **not** bounded by `L` — it keeps every lot that *any* particle still believes has a live unit in it, and only drops a lot from its own bookkeeping once *every* particle agrees it's fully spoiled (checked once per filter step, right after new arrivals are added). `L` only controls how many of the filter's *newest* lots get exported onto the wire, oldest-first truncation. Pick `L` too small, and a lot the filter still believes has live units in it — even units that have lost most of their freshness — can fall outside the exported window; the wire will under-report on-hand inventory even though the filter's own internal belief is completely fine. Pick `L` large enough to comfortably cover the peak number of concurrently open lots with live units, under whatever delivery cadence and spoilage dynamics are in play, and the truncation becomes harmless: the oldest exported lot is already fully dead in every particle (all-zero histogram row, zero `lot_counts` entry) by the time it would fall out of the window, so nothing real is ever dropped. The current production default is **`L = 50`** lot slots, with **`K = 30`** freshness bins by default.

**Caveat:** totals-only observations — the "books only" and "+ scan waste" scenarios on the observation ladder, where the store never reports which specific lot a sale or a piece of waste came from — cannot recover a lot's *within-lot* freshness shape from evidence alone. The histogram in that case leans heavily on the model's assumptions about newly arrived units' starting freshness and on the built-in gamma-process freshness decay, rather than on anything actually observed that day. `f_marginals` under totals-only channels mostly reflects the filter's prior freshness trajectory, not what the store reported.

## In the code

| Concept | Symbol / field | Location |
| --- | --- | --- |
| Flatten a particle bank onto the wire | `belief_flat_from_unit_bank` | `crates/voi_core/src/belief_flat.rs:32` |
| Freshness bin centers, `K` evenly spaced points in `[0,1]` | `f_grid` | `crates/voi_core/src/belief_flat.rs:17` ([`f_grid_k`](/api/rust/voi_core/belief_flat/fn.f_grid_k.html)) |
| Per-lot particle-weighted alive-unit count | `lot_counts[L]` | `crates/voi_core/src/belief_flat.rs:39`, `:59` |
| Per-lot freshness histogram, normalized | `f_marginals[L×K]` | `crates/voi_core/src/belief_flat.rs:40`, `:63`–`78` |
| Keep newest `L` filter lots, oldest-first truncation | `first_lot = n_lots.saturating_sub(l)` | `crates/voi_core/src/belief_flat.rs:37` |
| Filter's own internal lot retention (not bounded by `L`) | `prune_dead_prefix` | `crates/voi_core/src/unit_pf.rs:134` |
| Wire dimensions stored on the session | `l_dim`, `k_dim` | `crates/voi_core/src/session.rs:142`, `:144` |
| Default wire size: `L = 50` lot slots | `DEFAULT_L_DIM` | `crates/voi_core/src/params.rs:7` |
| Default wire size: `K = 30` freshness bins | `k_dim: DEFAULT_K_DIM` | `crates/voi_core/src/session.rs:239` |
| Guard test: legacy `tau_grid` / `age_marginals` never exported | `belief_flat_from_unit_bank_exports_f_wire_keys` | `crates/voi_core/src/belief_flat.rs:98` |
| Studio computes its W1 belief-accuracy score from this wire | — | `web/src/charts/beliefAccuracy.ts` |

## Caveats

**The wire is a lossy projection, not the belief.** Two particles (or two different filter runs) can produce identical `f_marginals` histograms for a lot while disagreeing completely about which specific units are fresh — the filter's real posterior carries correlation and identity information across units and across lots that the histogram export cannot represent. Any conclusion drawn from staring at the wire ("this lot looks mostly fresh") is a conclusion about the *aggregate*, not about any one unit.

**`L` and `K` are both fixed per session, not adaptive.** Neither dimension grows automatically to match how many lots are actually open or how peaked a distribution actually is; both are set once, when a session starts, and held fixed for its life. A workload with unusually long-lived lots or an unusually tight freshness distribution may need a larger `L` or `K` than the defaults to avoid truncation or coarse binning artifacts respectively.

**Alive-only normalization can mask a lot that is almost entirely dead.** Because `f_marginals` is normalized over alive units only, a lot with just one alive unit out of an original delivery of many still exports a full, normalized histogram — reading the histogram alone, without also checking the much smaller `lot_counts` value for that slot, can overstate how much inventory a lot actually represents.

**Studio freshness accuracy uses the 1-Wasserstein distance (W1) — a measure of how far apart two distributions are — computed on this wire, not on the raw particles.** Blueberry Studio's belief-accuracy "Distribution" cell scores the W1 distance between the rebinned wire histogram and the simulator's actual per-unit freshness values (ground truth: the simulator's true state, as opposed to what the filter believes). All-days is the mean of those per-day W1 values. Scoring unit counts with the Continuous Ranked Probability Score (CRPS) — which measures how well a full predictive distribution, not just its mean, matches what actually happened — would need the particle predictive $\{N^{(i)}\}$ (each particle's own count of alive units, not just their weighted average). This wire doesn't export that; it only exports the weighted average, $\mathbb{E}[N]$, via `lot_counts`. So the studio does not claim a count-CRPS score from the flattened payload.
