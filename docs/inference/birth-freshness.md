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

Each physical delivery carries **three lots** (`L = 3`). Under **LGTIN**, birth pushes
**three segments**, each from its own `ArrivalCondition` (`Duration(d_ℓ)` or
`Exposure(Λ_ℓ)` for that lot's record). Under **UPC**, birth pushes **one merged cohort**
of `Q` units from the equally weighted mixture
$\text{Law}_\text{UPC} = \frac{1}{L}\sum_\ell \text{Law}(\text{record}_\ell)$ — mixing
the laws, not averaging the dates, so between-lot spread survives as variance in the
cohort draw.

This page is about that conditioning step: what gets pinned down, what gets integrated
away, and how a particle can be born already dead with exactly the right probability.

## The idea

Think back to the cold-chain story: a delivery's freshness depends on how long the trip
took ($d$), how much **cold-chain break** damage accumulated along the way (discrete
episodes where product leaves refrigeration — dock staging, missed connections, doors
open), and where each individual berry happened to sit in the truck ($\psi$, drawn
separately per unit). Breaks punch warm pulses into an otherwise refrigerated trace; the
path-integrated exposure $\Lambda$ folds duration and temperature history together. A
per-unit position multiplier $\psi$ then gives one unit's personal exposure, which finally
becomes that unit's freshness through a random-loss draw.

A real store almost never observes all three pieces. A temperature logger that rode with
the pallet reveals the exact exposure $\Lambda$ for the lot (both $d$ and break damage
folded together via path integration) — but still nothing about $\psi$, which no
instrument ever measures. A pack date on the paperwork reveals only $d$, the calendar
duration, and says nothing about whether or where breaks occurred. Books-only scenarios
reveal neither. So the filter's birth draw has exactly three shapes, one per conditioning
depth, all consuming the *same* hierarchical model, just conditioned on a different
subset of what it happens to know:

- **Temperature-history scenario:** pin $\Lambda$ exactly (from the trace via
  `resolve_arrival_exposure`), integrate over $\psi$ only.
- **Pack-date scenarios** ("pack date on the ASN," "lot ID + pack date"): pin $d$,
  integrate over break realizations (via `thermal_nodes`) and $\psi$.
- **Books-only scenarios** ("books only," "shrink gun"): pin nothing — integrate over
  $d$, breaks, and $\psi$ all at once, using the corridor's own priors.

Because freshness is never observed directly, "birth" for the filter always means drawing
from a *distribution* over $f$, not a single number — even on the richest scenario. And
because that distribution can genuinely put positive probability mass on "already
spoiled," the filter has to be able to draw a unit born exactly at $f=0$, not just a unit
that happens to land very close to it.

## The math

Let $\Lambda$ (cumulative thermal exposure, reference-days) be a unit's personal exposure
as in the [cold-chain page](/store/cold-chain-arrival). Conditional on $\Lambda$,
freshness has the closed-form law

$$
P(f = 0 \mid \Lambda) = \gamma_q(k\Lambda,\ 1/\theta), \qquad P(f > x \mid \Lambda) = \gamma_p(k\Lambda,\ (1-x)/\theta) \quad (x \in (0,1))
$$

where $k$ (`gamma_shape`) and $\theta$ (`gamma_scale`) are the same calibrated constants
as arrival truth, and $\gamma_p,\gamma_q$ are the regularized lower/upper incomplete
gamma functions.

The filter never observes $\Lambda$ or $x$ directly for an individual unit; instead it
observes one of three conditions, and must marginalize the rest:

$$
\text{ArrivalCondition} \in \{\ \mathrm{Exposure}(\Lambda_{\text{obs}}),\ \ \mathrm{Duration}(d_{\text{obs}}),\ \ \mathrm{Prior}\ \}
$$

resolved per lot record, in this priority order: use `Exposure` if a temperature trace
exists for that lot (the temperature-history scenario); else `Duration` if a pack date
exists (a pack-date scenario); else fall back to the bare corridor `Prior` (a books-only
scenario). For F3, $\Lambda_{\text{obs}}$ is the **path-integrated** exposure from the
observed trace — the same Q10 integral the truth path uses — not a scalar fit to a
pre-drawn mean temperature.

Each condition defines a different marginal CDF over $f$, computed by weighted sums over
fixed quadrature grids. Duration and position still use the 8-node grids from
`data/abdella/arrival_model.json` (shared with truth generation, never resampled at
runtime). The thermal channel no longer integrates a truncated-normal mean transit
temperature; it **enumerates** break counts $N \sim \mathrm{Poisson}(\rho d)$ with
Poisson weights, and given $N \ge 1$ integrates the total break exposure
$\mathrm{Gamma}(N, m)$ with the same 8-node quadrature — $N = 0$ contributes one
deterministic node, for **33 thermal nodes** in total (`thermal_nodes`).

$$
F_{\mathrm{Exposure}(\Lambda)}(f) = \sum_j w_j \cdot P\big(f' \le f \mid \Lambda \cdot \psi(u_j)\big)
$$

$$
F_{\mathrm{Duration}(d)}(f) = \sum_{(\Lambda_t, w_t) \in \text{thermal\_nodes}(d)} \sum_j w_t w_j \cdot P\big(f' \le f \mid \Lambda_t \cdot \psi(u_j)\big)
$$

$$
F_{\mathrm{Prior}}(f) = \sum_h \sum_{(\Lambda_t, w_t) \in \text{thermal\_nodes}(d(u_h))} \sum_j w_h w_t w_j \cdot P\big(f' \le f \mid \Lambda_t \cdot \psi(u_j)\big)
$$

Each nested sum integrates out exactly the nuisance variables that condition doesn't pin
down: `Exposure` only needs $\psi$ integrated (one 8-point sum); `Duration` needs break
realizations and $\psi$ (33×8 = 264 evaluations per grid point); `Prior` needs $d$,
breaks, and $\psi$ all three (8×33×8 = 2 112 evaluations per grid point). This is a
*fixed, deterministic* product quadrature — not Monte Carlo — so the same condition
always produces the same marginal law, byte-for-byte, and Rust and Python builds can
never numerically diverge from each other on it. Laws are cached on a 512-point
`ARRIVAL_GRID` (down from 4096) at an inverse-sampling resolution of ~0.002 in freshness.

Under **LGTIN**, each of the three lots per delivery calls this machinery once with its
own resolved condition. Under **UPC**, the filter builds each component law, then mixes
CDFs pointwise: $\text{Law}_\text{UPC} = \frac{1}{L}\sum_\ell \text{Law}_\ell$.

Sampling from this marginal CDF has to handle the atom at $f=0$ correctly. The atom mass
is computed once in closed form,

$$
\pi_0 = F(0) = P(f=0 \mid \text{condition})
$$

then divided out of the CDF before inverting the *continuous* part:

$$
\tilde F(f) = \frac{F(f) - \pi_0}{1 - \pi_0}, \qquad f \in (0, 1]
$$

To draw one unit's birth freshness, draw $u \sim \mathrm{Uniform}(0,1)$; if $u < \pi_0$,
the unit is born at $f=0$ exactly; otherwise invert $\tilde F$ (linear interpolation on
the cached grid) to get $f \in (0,1]$. This two-step draw is what lets a spoiled-on-arrival
unit land at *exactly* zero with *exactly* probability $\pi_0$, rather than only
approximately near zero the way naive grid interpolation of the raw CDF would.

## Why it's modelled this way

**One hierarchical model, three conditioning depths — never three separate models.** A
date or a temperature trace reveals a *distribution* over $f$, not a scalar, and that
distribution is what seeds the lot. Deriving a single point-estimate freshness per
observation scenario and handing particles that scalar would throw away exactly the
uncertainty a richer scenario is supposed to *reduce*, so the whole point of comparing
scenarios on the knowledge ladder would be lost if birth collapsed to a number.

**Break enumeration, not a wider temperature draw.** Cold-chain damage concentrates at
handoffs. Enumerating Poisson break counts and gamma-distributed break totals gives the
temperature-history channel something real to learn once duration is known — the trace is
the generative primitive and $\Lambda$ is derived from it, not fit to a pre-drawn scalar
by bisection.

**The conditioning is deliberately joint, not marginal.** The temperature-history
scenario conditions on the full joint exposure $\Lambda$ from the trace, not a marginal
piece of it, because the trace's own timestamps already pin duration — re-integrating
over duration on that scenario would silently throw away real information and make the
richest scenario look less informative than the pack-date scenario. Getting the
conditioning structure right, not just the closed forms, is what makes the scenario
comparison honest.

**Mix the laws under UPC.** Three lots arrive with three possibly different pack dates or
exposures; a UPC store cannot attribute them, so birth uses an equally weighted mixture
of the three component laws. Averaging dates first would leave only within-lot variance
and understate UPC's true uncertainty.

**Closed-form atom over grid-approximated atom.** The atom $P(f=0\mid\Lambda)$ has an
exact closed form ($\gamma_q$) that costs nothing extra to compute, so it is computed once
and divided out of the sampling CDF rather than left to whatever mass a 512-point grid
happens to assign to its first bin. Building a finer CDF grid and hoping bin 0 converges
to the right mass would risk mispricing "already dead on arrival" for exactly the short,
high-exposure deliveries where that probability matters most.

**Caveat:** the quadrature is exact for the *assumed* families (shifted-gamma duration,
Poisson×gamma breaks, lognormal position), but those families are themselves
hand-authored and only roughly calibrated against six real shipments (see the
[cold-chain page](/store/cold-chain-arrival)'s caveats) — a wrong family shape would
propagate through every observation scenario's conditioning identically, since all three
share the same quadrature machinery and the same underlying model.

## In the code

| Concept | Symbol / name | Location |
| --- | --- | --- |
| Scenario-appropriate condition (Exposure / Duration / Prior) | `ArrivalCondition` | `crates/voi_core/src/arrival.rs:75` |
| Resolve which condition a delivery record implies | `resolve_arrival_f_law` | `crates/voi_core/src/unit_pf.rs:298` |
| Path-integrated exposure from temperature trace (F3) | $\Lambda_{\text{obs}}$ | `crates/voi_core/src/arrival.rs:2334` ([`resolve_arrival_exposure`](/api/rust/voi_core/arrival/fn.resolve_arrival_exposure.html)) |
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
partial-temperature-trace or noisy-pack-date condition in the production model. A real
supplier ASN with an uncertain or rounded pack date would be modeled as a clean
`Duration`, not as `Duration` plus extra noise.

**Nuisance integration assumes the corridor's own priors are correct.** Whatever the
condition doesn't pin down is integrated using the *model's* distributional assumptions
for that variable (e.g. the corridor's duration prior when only exposure is known, or the
assumed break-rate parameters when only duration is known) — if those assumed families
are wrong, the marginal CDF the filter births from is wrong in the same direction for
every particle, and no amount of particle diversity or resampling can correct a
systematically mis-integrated nuisance variable.

**Break parameters are assumed, not fit from the six Abdella shipments.** Those traces
cover a chain that never broke, so $\rho$ and $\bar\tau$ are design choices checked only
in the $\rho \to 0$ limit against the observed duration share — not maximum-likelihood
estimates from the six clean traces themselves.

**The quadrature is fixed and deterministic.** Thermal enumeration uses 33 nodes;
duration and position each use 8. This keeps books-only birth at 2 112 evaluations per
grid point — cheap enough for the studio's runtime budget, but still a deterministic
approximation to the true continuous integral, not the integral itself.
