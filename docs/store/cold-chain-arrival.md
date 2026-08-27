---
title: Cold-Chain Arrival Model
sources:
  code:
    - crates/voi_core/src/arrival.rs
    - crates/voi_core/src/shipments.rs
    - crates/voi_core/src/physics.rs
    - data/abdella/arrival_model.json
    - scripts/arrival_calibration_note.py
    - data/abdella/calibration_note.md
  adr: ["0149", "0150", "0148"]
---

# Cold-chain arrival model

Every delivery starts its life in the store already partway degraded, because it spent a day or several inside a truck before it ever reached a shelf. This page describes how the simulator turns "a shipment travelled through a refrigerated corridor" into a probability distribution over each unit's freshness `f` the moment it arrives. It matters because every observation scenario in the knowledge ladder — from books only through the full temperature-history scenario — is a different amount of information about the *same* underlying trip, not a different model. Get the generative story right here and the whole ladder's information gains become meaningful.

![Six Abdella cold-chain shipments (duration vs. mean temperature factor) plotted against the corridor families the arrival model assumes](/figures/cold-chain-arrival-calibration-overlay.png)

## The idea

Think of one delivery as a truck making one trip. Three things about the trip are shared by every berry on the truck:

1. **How long the trip took** — calendar transit duration `d`, drawn once per delivery from a shifted-gamma corridor law.
2. **What happened thermally along the way** — a piecewise temperature path built from deterministic cold-chain legs plus random **break events** (unrefrigerated dock time, missed connections, and similar handoffs). Cumulative thermal exposure **Λ** (lambda) is integrated out of that path, not drawn as a scalar first.
3. **Where on the pallet each berry rode** — a within-pallet position multiplier **ψ** (psi), drawn independently for every unit.

Multiplying the trip's shared exposure by a unit's personal **ψ** gives that unit's own exposure, which then feeds into the *same* random-degradation law used for in-store aging (a gamma-distributed loss). The result is a **freshness** `f` for that one unit — not a calendar clock, a state variable running from 1 (pristine) down to 0 (spoiled/dead).

So the model has one "corridor" story (duration and temperature path) shared across the whole delivery, and one "which pallet spot did this berry ride in" story that's private to each unit. No observation the store ever makes — not even a full temperature log — reveals that private per-unit story, which is why units from the very same lot can genuinely differ in freshness even under perfect knowledge of the trip's temperature history.

### Three lots per delivery (target model)

Under ADR 0149, each delivery carries **L = 3** fixed lots. Total case quantity is **split** across the three lots, not multiplied — per-day filter runtime stays flat. Each lot draws its own upstream journey (own duration, own break realization); one DC→store leg is shared:

$$
\Lambda_\ell = \Lambda_{\mathrm{upstream},\ell} + \Lambda_{\mathrm{shared}}
$$

Under **GSIN**, the filter holds three segments, each born from its own arrival law (`Duration(d_\ell)` or `Exposure(Λ_\ell)`). Under **UPC**, one cohort is born from the mixture `Law_UPC = (1/L) Σ_ℓ Law(record_ℓ)` — mix the laws, don't average the dates. On the current integrate branch the session may still mint one lot id per delivery; the three-lot DC model above is the target wiring described in ADR 0149 and the multi-lot plan.

### Planned v2 upgrade (design direction)

The transit generative v2 plan is the next thermal authority. It keeps compound-Poisson breaks and path-first Λ, and adds:

- **Bottom-up stage durations** — draw each leg's time first so total `d` matches the Abdella pooled law exactly, instead of fixed duration shares on a single `d` draw.
- **Trip thermal modes** — one per-trip draw among cool / nominal / warm offsets applied to all leg setpoints.
- **Hourly OU noise** on the path so temperature charts look like real loggers even when `ρ = 0`.
- **Unified duration family** — demote `short_haul` / `long_haul` studio chips; default everything through `abdella_all`.

Those v2 features are not on the integrate branch yet; the sections below describe what the code does today, with v2 called out where the design will change.

## The math

For one delivery drawn from a **corridor** (an arrival lane — `abdella_all` is the Abdella-matched fit; `short_haul` and `long_haul` are illustrative studio corridors), the truth-path generative model proceeds as follows.

### Duration

$$
d = d_{\min} + \mathrm{Gamma}(\text{delay\_shape}, \text{delay\_scale})
$$

$d$ is calendar transit duration in days, drawn once per delivery. $d_{\min}$, delay_shape, and delay_scale are properties of the chosen corridor.

### Cold-chain path and breaks

The baseline path walks three named legs in order, each holding a fixed setpoint for its share of $d$:

| Leg | Share $w_k$ | Setpoint $\mu_k$ |
| --- | --- | --- |
| `precool_staging` | 0.15 | 0.35 °C |
| `line_haul` | 0.60 | 2.58 °C |
| `dock_receiving` | 0.25 | 4.32 °C |

On top of that baseline, **break events** are drawn (ADR 0150):

$$
N \sim \mathrm{Poisson}(\rho \cdot d), \qquad
\tau_j \sim \mathrm{Exp}(\bar\tau) \text{ at fixed } T_{\mathrm{break}}
$$

Break start times are uniform on $[0, d]$; each break punches a rectangular pulse to $T_{\mathrm{break}}$ for duration $\tau_j$, clamped so total break time never exceeds $d$. The trip clock runs during breaks, so exposure is exact:

$$
\Lambda_{\mathrm{lot}} = d \cdot \varphi_{\mathrm{set}} + \sum_j \tau_j \cdot (\varphi_{\mathrm{break}} - \varphi_{\mathrm{set}})
$$

where $\varphi_{\mathrm{set}}$ is the duration-weighted Q10 factor of the leg baseline and $\varphi_{\mathrm{break}} = \phi(T_{\mathrm{break}})$. Given $N$, the break contribution is $\mathrm{Gamma}(N, m)$ with $m = \bar\tau \cdot (\varphi_{\mathrm{break}} - \varphi_{\mathrm{set}})$.

The temperature trace is built first in `shipments.rs::truth_transit_trace`; Λ is integrated back out via `resolve_arrival_exposure` — the trace is the generative primitive, not a decorative fit to a pre-drawn scalar.

**Retired:** the truncated-normal mean transit temperature (`mu_T`, `sigma_T`, `sample_truncated_normal`) and the bisection loop that used to force a trace to match a scalar $\bar\varphi$ already drawn. That path made temperature history nearly uninformative once pack date was known.

### Per-unit position and freshness

$$
\psi \sim \mathrm{LogNormal}(0, \sigma_{\text{pos}})
$$

$\psi$ is drawn **independently for every unit**.

$$
\Lambda = \Lambda_{\mathrm{lot}} \cdot \psi
$$

$$
D \sim \mathrm{Gamma}(k \cdot \Lambda,\ \theta), \qquad f = \max(0,\ 1 - D)
$$

$D$ is the per-unit degradation loss from the same shape-scaled gamma law used in-store. Conditional on $\Lambda$:

$$
P(f > x \mid \Lambda) = \gamma_p(k\Lambda,\ (1-x)/\theta), \qquad
P(f = 0 \mid \Lambda) = \gamma_q(k\Lambda,\ 1/\theta)
$$

### Live calibrated numbers (schema 2)

From `data/abdella/arrival_model.json`:

| Parameter | Symbol | Value |
| --- | --- | --- |
| Break temperature | $T_{\mathrm{break}}$ | 12.0 °C |
| Break hazard | $\rho$ | 0.08 /day |
| Mean break duration | $\bar\tau$ (`tau_bar`) | 0.5 days |
| Position spread | $\sigma_{\text{pos}}$ | 0.08 |
| Q10 coefficient | $q_{10}$ | 3.0 |
| Reference temperature | $T_{\mathrm{ref}}$ | 0.0 °C |
| Gamma shape | $k$ | 2.0 |
| Gamma scale | $\theta$ | 1/28 ≈ 0.035714 |
| Reference life | $\eta_{\text{ref}}$ | 14.0 reference-days |

Note $k \cdot \theta \cdot \eta_{\text{ref}} = 1$ — the calibration invariant tying mean loss rate to a 14-reference-day shelf life.

**Corridors** (shifted-gamma duration law):

| Corridor | $d_{\min}$ (days) | delay_shape | delay_scale |
| --- | --- | --- | --- |
| `short_haul` | 1.803 | 2.0 | 0.05 |
| `long_haul` | 4.033 | 1.628 | 0.814 |
| `abdella_all` | 1.853 | 3.009 | 0.974 |

`abdella_all` is moment-matched to the six Abdella shipments (ADR 0148); `short_haul` and `long_haul` are illustrative only.

$\rho$, $\bar\tau$, and $T_{\mathrm{break}}$ are **assumed scenario parameters**, not fit — all six real shipments are clean chains with no observed breaks.

## Why it's modelled this way

**Shape-scaling, not scale-scaling.** The daily in-store aging law and the arrival law both scale the gamma distribution's *shape* parameter by exposure ($\mathrm{Gamma}(k\Lambda, \theta)$), rather than its *scale*. Arrhenius kinetics describe a rate constant, meaning heat produces *more* degradation events of the same size, not the same number of *bigger* events. Shape-scaling is also what makes $\Lambda$ a genuine sufficient statistic for the whole trip — two journeys with equal $\Lambda$ but different temperature paths have the same freshness distribution under shape-scaling, but would differ under scale-scaling, which would mean a temperature log couldn't be summarized by one number at all.

**Break events instead of a wider temperature draw.** A truncated-normal "the truck ran a bit warm" knob inflates spread without a physical story and, at the fitted spread, left only ~1.6% of exposure variance for temperature once duration was known (`Var(log d) = 0.205` vs `Var(log \bar\varphi) = 0.00335` on the six shipments). Compound-Poisson breaks at a fixed break temperature raise the temperature channel's share of variance to a design target near 20% at default $\rho$, so F3 has something real to learn.

**Path first.** Integrating Λ from the trace makes the temperature-history observation channel observe the same object the simulator randomizes. The retired bisection trace was a rendering of scalars after the fact.

**Assumed vs fitted.** With only six refrigerated shipments, corridor durations are moment-matched; leg setpoints are chosen so the break-free limit matches the observed $\bar\varphi$ centre; break rate and duration are documented assumptions. An MLE fit on six points would over-read the data.

## In the code

| Concept | Symbol | Location |
| --- | --- | --- |
| Truth-path temperature trace (legs + breaks) | path → Λ | `crates/voi_core/src/shipments.rs:98` ([`truth_transit_trace`](/api/rust/voi_core/shipments/fn.truth_transit_trace.html)) |
| Exposure from observed path | Λ | `crates/voi_core/src/arrival.rs:1716` ([`resolve_arrival_exposure`](/api/rust/voi_core/arrival/fn.resolve_arrival_exposure.html)) |
| Truth draw: path then Λ | — | `crates/voi_core/src/arrival.rs:961` ([`draw_transit`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.draw_transit)) |
| Whole-delivery truth draw | $d$, trace, Λ; per-unit $\psi$/loss | `crates/voi_core/src/arrival.rs:1027` ([`draw_truth_delivery`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.draw_truth_delivery)) |
| Truth-path per-unit generative draw | $d$, breaks, $\psi$, $\Lambda$, $f$ | `crates/voi_core/src/arrival.rs:1001` ([`draw_unit_f`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.draw_unit_f)) |
| Break-free baseline factor | $\varphi_{\mathrm{set}}$ | `crates/voi_core/src/arrival.rs:732` ([`phi_set`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.phi_set)) |
| Closed-form Λ given break durations | — | `crates/voi_core/src/arrival.rs:764` ([`lambda_from_breaks`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.lambda_from_breaks)) |
| Filter: enumerate break counts + gamma quadrature | — | `crates/voi_core/src/arrival.rs:1247` ([`thermal_nodes`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.thermal_nodes)) |
| Q10 temperature factor | $\phi(T)$ | `crates/voi_core/src/physics.rs:38` ([`store_temp_factor`](/api/rust/voi_core/physics/fn.store_temp_factor.html)) |
| Tail probability given exposure | $P(f>x\mid\Lambda)$ | `crates/voi_core/src/arrival.rs:923` ([`p_f_gt_at`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.p_f_gt_at)) |
| Full CDF given exposure | $P(f\le x\mid\Lambda)$ | `crates/voi_core/src/arrival.rs:935` ([`cdf_f_given_lambda`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.cdf_f_given_lambda)) |
| Spoiled-on-arrival atom | $P(f=0\mid\Lambda)$ | `crates/voi_core/src/arrival.rs:950` ([`p_f_zero`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.p_f_zero)) |
| Gamma quantile (break enumeration) | — | `crates/voi_core/src/arrival.rs:535` (`gamma_dist_quantile`) |
| Position multiplier draw | $\psi$ | `crates/voi_core/src/arrival.rs:995` (`draw_psi_pos`) |
| Artifact fields: legs, $T_{\mathrm{break}}$, $\rho$, $\bar\tau$, corridors | — | `data/abdella/arrival_model.json`; parsed by `crates/voi_core/src/arrival.rs:449` ([`arrival_artifact_from_json`](/api/rust/voi_core/arrival/fn.arrival_artifact_from_json.html)) |
| Reporting overlay (no fitting) | six-shipment table + figure | `scripts/arrival_calibration_note.py`, `data/abdella/calibration_note.md` |

## Caveats

**Refrigerated-leg only — arrival freshness is an upper bound.** The model window runs from the first lot-mean temperature reading below 10 °C through the published end-of-chain point. Harvest-to-precool field heat — typically the most thermally damaging segment — is excluded. Real arrival freshness is therefore lower than what this model reports.

**No observation channel reveals a unit's actual freshness.** Even the richest channel — the full temperature-history trace — pins down shared exposure Λ for the delivery (or per-lot Λ under the three-lot target). It never reveals $\psi$ or the per-unit gamma draw $D$.

**Break parameters are assumed, not measured.** The six Abdella shipments never broke; $\rho$ and $\bar\tau$ are scenario knobs. At $\rho \to 0$ the model should recover the clean-chain duration dominance seen in the data; at default $\rho$ the duration share of $\mathrm{Var}(\log \Lambda)$ is a design output (~80%), not an Abdella measurement.

**Stage-1 vs v2.** Today's code uses fixed leg *shares* on a single $d$ draw. The v2 plan replaces that with bottom-up stage gammas, trip modes, and hourly path noise while keeping the same break law and filter caching strategy.
