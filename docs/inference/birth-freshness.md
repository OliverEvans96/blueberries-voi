---
title: Birth Freshness by Observation Scenario
sources:
  adr: ["0149", "0150"]
  code:
    - crates/voi_core/src/arrival.rs
    - crates/voi_core/src/unit_pf.rs
    - crates/voi_core/src/obs.rs
---

# Birth freshness: what each observation scenario conditions on

Every time a delivery arrives, the particle filter has to decide what freshness to hand the
units in that new lot — inside every one of its hundreds of hypothetical shelves. It can
never simply ask "how fresh did this lot actually arrive?", because no observation channel
on the [knowledge ladder](/ladder/observation-scenarios) reveals freshness directly.
What the filter *can* do is draw from the same generative story used to make the
[cold-chain arrival model](/store/cold-chain-arrival), but conditioned on whichever piece
of that story this scenario's channels actually handed it — a temperature trace, a pack
date, or nothing at all.

Each physical delivery carries three lots ($L = 3$). Under the **LGTIN** scenario — LGTIN
being a Global Trade Item Number (GTIN) plus a batch/lot number, a lot-level identifier for
one production batch of one trade item — birth pushes three segments, one per lot, each
from its own resolved condition (either a duration record or an exposure record for that
lot). Under a **Universal Product Code (UPC)** scenario, birth instead pushes one merged
cohort of $Q$ units (the number of units in that delivery) drawn from the equally weighted
mixture of the three lots' laws — mixing the laws, not averaging the dates, so between-lot
spread survives as variance in the cohort draw.

This page is about that conditioning step: what gets pinned down, what gets integrated
away, and how a particle can be born already dead with exactly the right probability.

## The idea

Think back to the cold-chain story: a delivery's freshness depends on how long the trip
took ($d$), how much cold-chain break damage accumulated along the way (discrete episodes
where product leaves refrigeration — dock staging, missed connections, doors open), and
where each individual berry happened to sit in the truck ($\psi$, drawn separately per
unit). Breaks punch warm pulses into an otherwise refrigerated trace; the path-integrated
exposure $\Lambda$ — a running total of thermal exposure over the whole trip — folds
duration and temperature history together. A per-unit position multiplier $\psi$ then gives
one unit's personal exposure, which finally becomes that unit's freshness through a
random-loss draw.

A real store almost never observes all three pieces. A temperature logger that rode with
the pallet reveals the exact exposure $\Lambda$ for the lot (both $d$ and break damage
folded together via path integration) — but still nothing about $\psi$, which no
instrument ever measures. A pack date on the delivery paperwork — the Advance Ship Notice,
or ASN — reveals only $d$, the calendar duration, and says nothing about whether or where
breaks occurred. The books-only and scan-waste scenarios reveal neither. So the filter's
birth draw has exactly three shapes, one per conditioning depth, all consuming the *same*
hierarchical model, just conditioned on a different subset of what it happens to know:

- **The temperature-history scenario:** pin $\Lambda$ exactly, computed directly from the
  observed trace, and integrate over $\psi$ only.
- **The pack-date and LGTIN scenarios** (delivery history includes a pack date but no
  temperature trace): pin $d$, and integrate over break realizations and $\psi$.
- **The books-only and scan-waste scenarios** (no delivery history at all): pin nothing —
  integrate over $d$, breaks, and $\psi$ all at once, using the corridor's own priors. (A
  corridor is the shipping-route / transit-assumption profile a delivery uses; its "priors"
  are just the model's default assumptions for that route when no specific evidence
  overrides them.)

Because freshness is never observed directly, "birth" for the filter always means drawing
from a *distribution* over $f$ (freshness), not a single number — even on the richest
scenario. And because that distribution can genuinely put positive probability mass on
"already spoiled," the filter has to be able to draw a unit born exactly at $f=0$, not just
a unit that happens to land very close to it.

## The math

Let $\Lambda$ (cumulative thermal exposure, in reference-days) be a unit's personal exposure
as in the [cold-chain page](/store/cold-chain-arrival). Conditional on $\Lambda$,
freshness has the closed-form law

$$
P(f = 0 \mid \Lambda) = \gamma_q(k\Lambda,\ 1/\theta), \qquad P(f > x \mid \Lambda) = \gamma_p(k\Lambda,\ (1-x)/\theta) \quad (x \in (0,1))
$$

where $k$ and $\theta$ are the same calibrated shape and scale constants used for the true,
simulated arrival process, and $\gamma_p,\gamma_q$ are the regularized lower/upper
incomplete gamma functions — standard statistical functions for computing gamma-distribution
probabilities.

The filter never observes $\Lambda$ or $x$ directly for an individual unit; instead it
observes one of three conditions, and must marginalize (average out) the rest:

$$
\text{ArrivalCondition} \in \{\ \mathrm{Exposure}(\Lambda_{\text{obs}}),\ \ \mathrm{Duration}(d_{\text{obs}}),\ \ \mathrm{Prior}\ \}
$$

resolved per lot record, in this priority order: use the exposure condition if a
temperature trace exists for that lot (the temperature-history scenario); else the duration
condition if a pack date exists (the pack-date or LGTIN scenario); else fall back to the
bare corridor prior (the books-only or scan-waste scenario). For the temperature-history
scenario, $\Lambda_{\text{obs}}$ is the path-integrated exposure computed directly from the
observed trace — the same calculation the truth path uses to accumulate spoilage risk from
temperature over time, following the Q10 rule (an Arrhenius-style rule from food science:
spoilage roughly multiplies by Q10 for every 10°C rise in temperature; Q10 = 2.0 here, so
spoilage roughly doubles) — not a scalar fit to a pre-drawn mean temperature.

Each condition defines a different marginal cumulative distribution function (CDF) over
$f$ — the probability that freshness is at or below a given value — computed by weighted
sums over fixed quadrature grids (a numerical-integration technique that approximates an
integral as a weighted sum over a small set of representative points). Duration and
position still use 8-point grids from a calibration file shared with truth generation and
never resampled at runtime. The thermal channel no longer integrates a truncated-normal
mean transit temperature. Instead it enumerates break counts — how many cold-chain breaks
occurred, $N$, drawn from a Poisson distribution with rate $\rho d$ (a break rate times the
trip duration) — and, given at least one break occurred, integrates the total break
exposure from a Gamma distribution with $N$ breaks and mean per-break severity $m$, using
the same 8-node quadrature. Zero breaks contributes one deterministic node, for 33 thermal
nodes in total.

$$
F_{\mathrm{Exposure}(\Lambda)}(f) = \sum_j w_j \cdot P\big(f' \le f \mid \Lambda \cdot \psi(u_j)\big)
$$

$$
F_{\mathrm{Duration}(d)}(f) = \sum_{(\Lambda_t, w_t) \in \text{thermal\_nodes}(d)} \sum_j w_t w_j \cdot P\big(f' \le f \mid \Lambda_t \cdot \psi(u_j)\big)
$$

$$
F_{\mathrm{Prior}}(f) = \sum_h \sum_{(\Lambda_t, w_t) \in \text{thermal\_nodes}(d(u_h))} \sum_j w_h w_t w_j \cdot P\big(f' \le f \mid \Lambda_t \cdot \psi(u_j)\big)
$$

In each sum, $u_j$ is a quadrature node (one of the representative sample points) and $w_j$
its weight; $\psi(u_j)$ is the per-unit position multiplier evaluated at that node; and
$(\Lambda_t, w_t)$ is a thermal node — a candidate total break exposure and its weight,
drawn from the break-count enumeration above. Each nested sum integrates out exactly the
nuisance variables that the condition doesn't pin down. The exposure condition only needs
$\psi$ integrated, an 8-point sum. The duration condition needs break realizations and
$\psi$ integrated together, 33 × 8 = 264 evaluations per grid point. The prior condition
needs duration, breaks, and $\psi$ all three integrated, 8 × 33 × 8 = 2,112 evaluations per
grid point.

This is a fixed, deterministic product quadrature — not a random (Monte Carlo) simulation —
so the same condition always produces the same marginal law, and the Rust and Python builds
are tested to match on it. Laws are cached on a 512-point grid at an inverse-sampling
resolution of about 0.002 in freshness.

Under the LGTIN scenario, each of the three lots per delivery calls this machinery once
with its own resolved condition. Under a UPC scenario, the filter builds each component
law, then mixes the CDFs pointwise: $\text{Law}_\text{UPC} = \frac{1}{L}\sum_\ell \text{Law}_\ell$.

Sampling from this marginal CDF has to handle the atom at $f=0$ correctly — "atom" meaning
all the probability concentrated on that single value, with no spread, representing units
born already spoiled. The atom mass is computed once in closed form,

$$
\pi_0 = F(0) = P(f=0 \mid \text{condition})
$$

then divided out of the CDF before inverting the *continuous* part:

$$
\tilde F(f) = \frac{F(f) - \pi_0}{1 - \pi_0}, \qquad f \in (0, 1]
$$

To draw one unit's birth freshness, draw $u \sim \mathrm{Uniform}(0,1)$ (a uniformly random
number between 0 and 1); if $u < \pi_0$, the unit is born at $f=0$ exactly; otherwise invert
$\tilde F$ (linear interpolation on the cached grid) to get $f \in (0,1]$. This two-step
draw is what lets a spoiled-on-arrival unit land at *exactly* zero with *exactly*
probability $\pi_0$, rather than only approximately near zero the way naive grid
interpolation of the raw CDF would.

## Why it's modelled this way

**One hierarchical model, three conditioning depths — never three separate models.** A
date or a temperature trace reveals a *distribution* over freshness, not a single number,
and that distribution is what seeds the lot. Deriving a single point-estimate freshness per
observation scenario and handing particles that number would throw away exactly the
uncertainty a richer scenario is supposed to *reduce*. The whole point of comparing
scenarios on the observation ladder would be lost if birth collapsed to a single number.

**Break enumeration, not a wider temperature draw.** Cold-chain damage concentrates at
handoffs. Enumerating Poisson break counts and gamma-distributed break totals gives the
temperature-history channel something real to learn once duration is known — the trace is
the generative primitive and $\Lambda$ is derived from it, not fit to a pre-drawn scalar
by trial and error.

**The conditioning is deliberately joint, not marginal.** The temperature-history
scenario conditions on the full joint exposure $\Lambda$ from the trace, not a marginal
piece of it, because the trace's own timestamps already pin duration. Re-integrating over
duration on that scenario would silently throw away real information and make the richest
scenario look less informative than the pack-date scenario. Getting the conditioning
structure right, not just the closed forms, is what makes the scenario comparison honest.

**Mix the laws under UPC.** Three lots arrive with three possibly different pack dates or
exposures; a UPC store cannot tell them apart, so birth uses an equally weighted mixture
of the three component laws. Averaging the dates first would leave only within-lot
variance and understate a UPC store's true uncertainty.

**Closed-form atom over grid-approximated atom.** The atom $P(f=0\mid\Lambda)$ has an
exact closed form that costs nothing extra to compute, so it is computed once and divided
out of the sampling CDF rather than left to whatever mass a 512-point grid happens to
assign to its first bin. Building a finer CDF grid and hoping bin zero converges to the
right mass would risk mispricing "already dead on arrival" for exactly the short,
high-exposure deliveries where that probability matters most.

**Caveat:** the quadrature is exact for the *assumed* families (a shifted-gamma duration
distribution, Poisson-times-gamma breaks, a lognormal position distribution), but those
families are themselves hand-authored and only roughly calibrated against six real
shipments — the Abdella dataset, six real refrigerated shipments used to calibrate
corridor timing (see the [cold-chain page](/store/cold-chain-arrival)'s caveats). A wrong
family shape would propagate through every observation scenario's conditioning
identically, since all three share the same quadrature machinery and the same underlying
model.

## In the code

| Concept | Symbol / name | Location |
| --- | --- | --- |
| Scenario-appropriate condition (Exposure / Duration / Prior) | `ArrivalCondition` | `crates/voi_core/src/arrival.rs:75` |
| Resolve which condition a delivery record implies | `resolve_arrival_f_law` | `crates/voi_core/src/unit_pf.rs:298` |
| Path-integrated exposure from temperature trace (temperature-history scenario) | $\Lambda_{\text{obs}}$ | `crates/voi_core/src/arrival.rs:2334` ([`resolve_arrival_exposure`](/api/rust/voi_core/arrival/fn.resolve_arrival_exposure.html)) |
| Break-count thermal enumeration (replaces truncated-normal quadrature) | `thermal_nodes_for_key` | `crates/voi_core/src/arrival.rs:1633` |
| Pack-date duration on the filter wire | `FilterObs.pack_date_days` | `crates/voi_core/src/obs.rs:107` |
| Marginal CDF over $f$ for a condition | `marginal_cdf_at` | `crates/voi_core/src/arrival.rs:1750` |
| Closed-form atom at $f=0$ | $\pi_0 = \gamma_q(k\Lambda, 1/\theta)$ | `crates/voi_core/src/arrival.rs:1324` ([`p_f_zero`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.p_f_zero)) |
| Cached, atom-divided CDF for inverse-CDF sampling | `build_law_cdf` | `crates/voi_core/src/arrival.rs:1923` |
| Draw one unit's birth freshness from the cache | `sample_unit_f_from_cache` | `crates/voi_core/src/arrival.rs:2036` |
| LGTIN: draw one lot's units under one condition | `sample_filter_birth_units` | `crates/voi_core/src/arrival.rs:2069` |
| UPC: equally weighted mixture of lot laws | `mixture_law` / `mixture_cache` | `crates/voi_core/src/arrival.rs:2098` / `2132` |
| UPC: draw merged cohort from mixture | `sample_filter_birth_units_mixture` | `crates/voi_core/src/arrival.rs:2149` |
| Birth stage in the daily filter step | (step 3) | `crates/voi_core/src/unit_pf.rs:707`–`786` |
| Duration / position quadrature nodes (8-point, version-pinned) | `quad_nodes`, `quad_weights` | `data/abdella/arrival_model.json` |
| Inverse-sampling grid resolution | `ARRIVAL_GRID` (= 512) | `crates/voi_core/src/arrival.rs:55` |

## Caveats

**Only three conditioning depths exist — nothing in between.** An observation scenario
either gives the filter the full exposure, a bare duration, or nothing; there is no
partial-temperature-trace or noisy-pack-date condition in the model as built. A real
supplier Advance Ship Notice (ASN) with an uncertain or rounded pack date would be modeled
as a clean duration, not as a duration plus extra noise.

**Nuisance integration assumes the corridor's own priors are correct.** Whatever the
condition doesn't pin down is integrated using the model's own distributional assumptions
for that variable — for example, the corridor's duration prior when only exposure is
known, or the assumed break-rate parameters when only duration is known. If those assumed
families are wrong, the marginal CDF the filter births from is wrong in the same direction
for every particle, and no amount of particle diversity or resampling can correct a
systematically mis-integrated nuisance variable.

**Break parameters are assumed, not fit from the six Abdella shipments.** Those traces
cover a chain that never broke, so the break rate and mean break duration are design
choices, checked only in the limit of no breaks against the observed duration share — not
maximum-likelihood estimates from the six clean traces themselves.

**The quadrature is fixed and deterministic.** Thermal enumeration uses 33 nodes;
duration and position each use 8. This keeps books-only birth at 2,112 evaluations per
grid point — cheap enough for the project's runtime budget, but still a deterministic
approximation to the true continuous integral, not the integral itself.
