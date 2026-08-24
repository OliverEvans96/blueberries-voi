---
title: Why a particle filter
sources:
  code: [crates/voi_core/src/unit_pf.rs, crates/voi_core/src/physics.rs, crates/voi_core/src/unit_ll.rs, crates/voi_core/src/session.rs]
---

# Why a particle filter

The store never sees the shelf directly — only sales, and sometimes waste counts or a lot ID. Turning those partial signals into a belief about what's actually on the shelf requires something that represents "what the shelf plausibly looks like right now" and updates that representation as each day's numbers come in. The model's state doesn't look like the smooth, single-hump distributions most textbook filters assume, so the choice of filtering method follows from the shape of the state itself.

![A particle-filter belief over freshness bins on one real episode day: several separated bars of probability mass, not a single smooth bump, with almost no mass anywhere near the true value](/figures/freshness-marginal-non-gaussian.png)

This is an actual filter output (books-only observations, day 24 of an episode): the freshness marginal across bins is lumpy and multi-modal, not a bell curve, and can sit far from the true freshness (dashed line) when observations are sparse — exactly the kind of shape a Gaussian summary would flatten out.

## The idea

Picture the true state of a shelf as a long list of numbers, one per unit currently on it: each unit's freshness $f$, somewhere between 1 (pristine) and 0 (spoiled). That list is not a single smooth curve summarized by a mean and a spread. Three things make it awkward:

- **A pile-up at zero.** A unit doesn't fade gradually into "spoiled" — it crosses a threshold and is dead. The state has a literal spike of probability sitting at $f=0$, not a thin tail. A bell curve can't represent a spike.
- **Sales are a lottery without replacement.** Each day, some units get bought and removed from the shelf, and fresher units are more likely to be picked. That's drawing distinct items from a finite basket — closer to shuffling a deck than to adding noise to a number.
- **Spoilage is a threshold, not a gentle decay.** Whether a unit dies today depends on whether its freshness happened to cross zero today, a discrete yes/no event for every unit on the shelf.

A filter that assumes the state is a single smooth, symmetric bump (the working assumption behind Kalman-style filters) would have to iron out the spike at zero and the discreteness of "who got picked" to fit that shape — throwing away exactly the structure that matters for deciding when to reorder. Writing down the state's distribution exactly, unit by unit, also gets expensive fast: with many units spread across several lots, there are far too many ways sales and spoilage could have played out to enumerate.

The practical alternative is to stop trying to describe the state with a formula and instead keep a **crowd of complete, concrete guesses** — call each one a *particle*. Each particle is one fully-specified hypothetical shelf: a freshness value for every unit that could be alive right now. Every day, each particle is aged forward, has sales and spoilage applied to it the same combinatorial way the real shelf would experience them, and is then scored against what was actually observed — particles whose story matches the observations better are kept more heavily, in proportion to how well they explain the data. With enough particles, the crowd's shape approximates the true state's shape — spike at zero, discreteness, and all — without writing that shape down as a formula.

## The math

The filter's job each day is to turn yesterday's belief into today's belief given the new observation $y_t$ (sales, and possibly waste or lot IDs):

$$
p(x_t \mid y_{1:t}) \;\propto\; p(y_t \mid x_t)\, p(x_t \mid x_{t-1})
$$

where $x_t$ is the full shelf state (every live unit's freshness $f$, grouped into lots). A particle filter approximates this posterior with $N$ weighted particles $\{x_t^{(i)}, w_t^{(i)}\}_{i=1}^N$:

$$
p(x_t \mid y_{1:t}) \;\approx\; \sum_{i=1}^{N} w_t^{(i)}\, \delta\!\left(x_t - x_t^{(i)}\right)
$$

Each day, every particle is aged forward under the same gamma-decrement process the ground truth uses, sales and spoilage are applied consistently with what was actually observed, and its weight $w_t^{(i)}$ is updated by how well that particle's story matches the day's observation:

$$
w_t^{(i)} \;\propto\; w_{t-1}^{(i)} \cdot p\!\left(y_t \mid x_t^{(i)}\right)
$$

Periodically the particles are **resampled** — particles with tiny weight are dropped and particles with large weight are duplicated — so the crowd keeps tracking the informative region of the state space instead of collapsing its weight onto one lucky particle. In this codebase that's `systematic_resample`, used inside `filter_step_unit` in `unit_pf.rs`.

No Gaussian, no closed-form update: the point mass at $f=0$, the without-replacement sales draw, and the threshold spoilage event are all represented directly by what the particles do, not approximated away by an assumed shape.

## Why it's modelled this way

The unit-level, freshness-native particle filter (`unit_pf.rs`) runs the real generative process directly — gamma aging per unit, freshness-weighted picking, spoilage at $f \le 0$ — at production speed (roughly 12 ms/day for 200 particles at a modest shelf size). There's no accuracy-for-speed trade to make here: exact particle-level simulation of the real process is already fast enough.

**Alternative considered: a cohort/age abstraction with an analytic survival curve.** Tracking a lot as a single count-and-age pair, with a Weibull survival curve standing in for spoilage, doesn't match the picking and spoilage physics unit-for-unit — a cohort abstraction can't represent that different units within the same lot drift apart in freshness and die individually, which is exactly what a richer observation channel (per-lot waste or sales counts) needs to be informative about.

**Alternative considered: grid/exact enumeration of the joint state.** Feasible in principle for a single lot, but the state space grows combinatorially with the number of live units and lots, and production shelves carry several lots of roughly 15 units each simultaneously.

**Caveat:** a particle filter is an approximation, not an exact posterior. Its fidelity depends on having enough particles ($N=200$ by default, `session.rs`) to cover the state space, and on resampling often enough to avoid weight collapse. It also costs more per step than a closed-form filter would, which is why this design only makes sense because the per-day compute budget comfortably absorbs that cost.

## In the code

| Concept | Symbol / name | File:line |
|---|---|---|
| Particle bank (the crowd of hypothetical shelves) | `UnitParticleBank` | `crates/voi_core/src/unit_pf.rs:51` |
| Per-particle freshness state | `freshness: Vec<Vec<f64>>` | `crates/voi_core/src/unit_pf.rs:53` |
| Per-particle weight | `weights: Vec<f64>` | `crates/voi_core/src/unit_pf.rs:52` |
| One filtering step (age, apply evidence, reweight) | `filter_step_unit` | `crates/voi_core/src/unit_pf.rs:404` |
| Resampling the crowd | `systematic_resample` | `crates/voi_core/src/unit_pf.rs:221` |
| Threshold spoilage event ($f \le 0$ is dead) | `apply_gamma_aging_independent` | `crates/voi_core/src/physics.rs:245` |
| Freshness-weighted, without-replacement sales draw | `sequential_kernel_path_logprob` | `crates/voi_core/src/unit_ll.rs:281` |
| Default particle count | `n_particles` (default 200) | `crates/voi_core/src/session.rs:1066`, `crates/voi_core/src/session.rs:1765` |

## Caveats

A particle filter trades exactness for tractability: it's an approximate posterior built from a finite sample, so it can lose track of low-probability but real scenarios if too few particles land near them, and its accuracy is only as good as the resampling schedule and particle count allow. It also doesn't explain *why* the state has this shape (that's the arrival and aging model, covered elsewhere) — this page only justifies the choice of inference method given that shape.
