---
title: Birth Freshness by Rung
sources:
  adr: [130, 144]
  code:
    - crates/voi_core/src/arrival.rs
    - crates/voi_core/src/unit_pf.rs
    - crates/voi_core/src/obs.rs
---

# Birth freshness: what each rung conditions on

Every time a delivery arrives, the particle filter has to decide what freshness to hand the units in that new lot — inside every one of its hundreds of hypothetical shelves. It can never simply ask "how fresh did this lot actually arrive?", because no observation channel on the [knowledge ladder](/ladder/rungs) reveals freshness directly. What the filter *can* do is draw from the same generative story used to make the [cold-chain arrival model](/store/cold-chain-arrival), but conditioned on whichever piece of that story this rung's channels actually handed it — a temperature trace, a pack date, or nothing at all. This page is about that conditioning step: what gets pinned down, what gets integrated away, and how a particle can be born already dead with exactly the right probability.

> **Figure (coming soon):** three small panels, one per rung family (F3 / F2·F2a / P0·P1), each showing the same arrival CDF over `f ∈ [0,1]` narrowing as more of the hierarchy gets pinned down by the observed evidence, with the `f=0` atom drawn as a filled dot at the CDF's left edge.

## The idea

Think back to the cold-chain story: a delivery's freshness depends on how long the trip took ($d$), how warm the truck ran on average ($\bar\varphi$, a temperature-driven multiplier), and where each individual berry happened to sit in the truck ($\psi$, drawn separately per unit). Multiplying the first two gives the *lot's* shared cumulative thermal exposure, $\Lambda$; multiplying in $\psi$ gives one *unit's* personal exposure, which finally becomes that unit's freshness through a random-loss draw.

A real store almost never observes all three pieces. A temperature logger that rode with the pallet reveals the exact exposure $\Lambda$ for the lot (both $d$ and $\bar\varphi$ folded together) — but still nothing about $\psi$, which no instrument ever measures. A pack date on the paperwork reveals only $d$, the calendar duration, and says nothing about how warm the truck ran. Books-only rungs reveal neither. So the filter's birth draw has exactly three shapes, one per rung family, all consuming the *same* hierarchical model, just conditioned on a different subset of what it happens to know:

- **F3** (temperature history): pin $\Lambda$ exactly, integrate over $\psi$ only.
- **F2 / F2a** (pack date): pin $d$, integrate over $\bar\varphi$ (via mean transit temperature) and $\psi$.
- **P0 / P1** (books only): pin nothing — integrate over $d$, $\bar\varphi$, and $\psi$ all at once, using the corridor's own priors.

Because freshness is never observed directly, "birth" for the filter always means drawing from a *distribution* over $f$, not a single number — even on the richest rung. And because that distribution can genuinely put positive probability mass on "already spoiled," the filter has to be able to draw a unit born exactly at $f=0$, not just a unit that happens to land very close to it.

## The math

Let $\Lambda$ (cumulative thermal exposure, reference-days) be a unit's personal exposure as in the [cold-chain page](/store/cold-chain-arrival). Conditional on $\Lambda$, freshness has the closed-form law

$$
P(f = 0 \mid \Lambda) = \gamma_q(k\Lambda,\ 1/\theta), \qquad P(f > x \mid \Lambda) = \gamma_p(k\Lambda,\ (1-x)/\theta) \quad (x \in (0,1))
$$

where $k$ (`gamma_shape`) and $\theta$ (`gamma_scale`) are the same calibrated constants as arrival truth, and $\gamma_p,\gamma_q$ are the regularized lower/upper incomplete gamma functions.

The filter never observes $\Lambda$ or $x$ directly for an individual unit; instead it observes one of three conditions, and must marginalize the rest:

$$
\text{ArrivalCondition} \in \{\ \mathrm{Exposure}(\Lambda_{\text{obs}}),\ \ \mathrm{Duration}(d_{\text{obs}}),\ \ \mathrm{Prior}\ \}
$$

resolved per delivery, in this priority order: use `Exposure` if a temperature trace exists for the delivery (F3); else `Duration` if a pack date exists (F2 / F2a); else fall back to the bare corridor `Prior` (P0 / P1). Each condition defines a different marginal CDF over $f$, computed by weighted sums over a fixed quadrature grid $\{(u_j, w_j)\}$ (8 nodes, from `data/abdella/arrival_model.json`, shared with truth generation and never resampled at runtime):

$$
F_{\mathrm{Exposure}(\Lambda)}(f) = \sum_j w_j \cdot P\big(f' \le f \mid \Lambda \cdot \psi(u_j)\big)
$$

$$
F_{\mathrm{Duration}(d)}(f) = \sum_i \sum_j w_i w_j \cdot P\big(f' \le f \mid d\cdot\bar\varphi(\bar T(u_i))\cdot\psi(u_j)\big)
$$

$$
F_{\mathrm{Prior}}(f) = \sum_h \sum_i \sum_j w_h w_i w_j \cdot P\big(f' \le f \mid d(u_h)\cdot\bar\varphi(\bar T(u_i))\cdot\psi(u_j)\big)
$$

Each nested sum integrates out exactly the nuisance variables that condition doesn't pin down: `Exposure` only needs $\psi$ integrated (one 8-point sum); `Duration` needs $\bar T$ and $\psi$ (8×8 = 64 evaluations); `Prior` needs $d$, $\bar T$, and $\psi$ all three (8×8×8 = 512 evaluations). This is a *fixed, deterministic* product quadrature — not Monte Carlo — so the same condition always produces the same marginal law, byte-for-byte, and Rust and Python builds can never numerically diverge from each other on it.

Sampling from this marginal CDF has to handle the atom at $f=0$ correctly. The atom mass is computed once in closed form,

$$
\pi_0 = F(0) = P(f=0 \mid \text{condition})
$$

then divided out of the CDF before inverting the *continuous* part:

$$
\tilde F(f) = \frac{F(f) - \pi_0}{1 - \pi_0}, \qquad f \in (0, 1]
$$

To draw one unit's birth freshness, draw $u \sim \mathrm{Uniform}(0,1)$; if $u < \pi_0$, the unit is born at $f=0$ exactly; otherwise invert $\tilde F$ (linear interpolation on a 4096-point grid) to get $f \in (0,1]$. This two-step draw is what lets a spoiled-on-arrival unit land at *exactly* zero with *exactly* probability $\pi_0$, rather than only approximately near zero the way naive grid interpolation of the raw CDF would.

## Why it's modelled this way

**One hierarchical model, three conditioning depths — never three separate models.** ADR 0144 is explicit that a date or a temperature trace reveals a *distribution* over $f$, not a scalar: "That distribution, not a scalar, is what seeds the lot." The alternative — deriving a single point-estimate freshness per rung and handing particles that scalar — was the design this remodel replaced. A point estimate throws away exactly the uncertainty a richer rung is supposed to *reduce*, so the whole point of comparing rungs on the knowledge ladder would be lost if birth collapsed to a number.

**The rung table is deliberately joint, not marginal.** An earlier draft of this design had F3 pin only $\bar T$ and integrate over duration "if unobserved" — a bug later corrected (ADR 0144, "Correction 1") once it was noticed that F3 already knows duration exactly (it's derived from the trace's own timestamps), so re-integrating over it silently threw away real information and made the richest rung look less informative than F2. The fix was to condition F3 on the full joint exposure $\Lambda$, not a marginal piece of it — a reminder that getting the conditioning structure right, not just the closed forms, is what makes the rung comparison honest.

**Closed-form atom over grid-approximated atom.** The atom $P(f=0\mid\Lambda)$ has an exact closed form ($\gamma_q$) that costs nothing extra to compute, so it is deliberately computed once and divided out of the sampling CDF rather than left to whatever mass a 4096-point grid happens to assign to its first bin. The rejected alternative — just building a finer CDF grid and hoping bin 0 converges to the right mass — would silently misprice "already dead on arrival" for exactly the short, high-exposure deliveries where that probability matters most.

**Honest caveat:** the quadrature is exact for the *assumed* families (shifted-gamma duration, truncated-normal temperature, lognormal position) but those families are themselves hand-authored and only roughly calibrated against six real shipments (see the [cold-chain page](/store/cold-chain-arrival)'s caveats) — a wrong family shape would propagate through every rung's conditioning identically, since all three share the same quadrature machinery and the same underlying model.

## In the code

| Concept | Symbol / name | Location |
| --- | --- | --- |
| Rung-appropriate condition (Exposure / Duration / Prior) | `ArrivalCondition` | `crates/voi_core/src/arrival.rs:25` |
| Resolve which condition a delivery's observation implies | `resolve_arrival_f_law` | `crates/voi_core/src/unit_pf.rs:287` |
| Exact temperature-trace exposure (F3) | $\Lambda_{\text{obs}}$ | `crates/voi_core/src/arrival.rs:776` (`resolve_arrival_exposure`) |
| Pack-date duration (F2 / F2a) | `obs.pack_date_days` | `crates/voi_core/src/obs.rs:68` |
| Marginal CDF over $f$ for a condition, via product quadrature | `marginal_cdf_at` | `crates/voi_core/src/arrival.rs:507` |
| Closed-form atom at $f=0$ | $\pi_0 = \gamma_q(k\Lambda, 1/\theta)$ | `crates/voi_core/src/arrival.rs:426` (`p_f_zero`) |
| Cached, atom-divided CDF for inverse-CDF sampling | `build_law_cdf` | `crates/voi_core/src/arrival.rs:621` |
| Draw one unit's birth freshness from the cache | `sample_unit_f_from_cache` | `crates/voi_core/src/arrival.rs:672` |
| Draw a whole lot's birth freshness for one particle | `sample_filter_birth_units` | `crates/voi_core/src/arrival.rs:703` |
| Quadrature nodes/weights (8-point, version-pinned) | `quad_nodes`, `quad_weights` | `data/abdella/arrival_model.json` |
| Filter calls the birth draw, one lot segment per delivery | (birth stage, step 3) | `crates/voi_core/src/unit_pf.rs:524`–`554` |

## Caveats

**Only three conditioning depths exist — nothing in between.** A rung either gives the filter the full exposure, a bare duration, or nothing; there is no partial-temperature-trace or noisy-pack-date condition in the production model. A real supplier ASN with an uncertain or rounded pack date would be modeled as a clean `Duration`, not as `Duration` plus extra noise.

**Nuisance integration assumes the corridor's own priors are correct.** Whatever the condition doesn't pin down is integrated using the *model's* distributional assumptions for that variable (e.g. the corridor's duration prior when only exposure is known) — if those assumed families are wrong, the marginal CDF the filter births from is wrong in the same direction for every particle, and no amount of particle diversity or resampling can correct a systematically mis-integrated nuisance variable.

**The quadrature is fixed at 8 nodes per dimension.** This keeps P0/P1 birth at 512 evaluations per delivery — cheap, but it is a deterministic approximation to the true continuous integral, not the integral itself; it is accurate enough for the studio's runtime budget, not proven to be accurate to arbitrary precision.
