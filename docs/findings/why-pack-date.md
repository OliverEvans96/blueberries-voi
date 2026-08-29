---
title: Why a pack date does so much
sources:
  adr:
    - "0149"
    - "0150"
  code:
    - crates/voi_core/src/arrival.rs
    - crates/voi_core/src/shipments.rs
    - data/abdella/arrival_model.json
    - scripts/fit_abdella_arrival.py
---

# Why a pack date does so much

[The previous finding](./does-belief-sharpen) showed that adding a supplier pack date to
the delivery record cuts belief error roughly 3× — the largest single step on the whole
knowledge ladder — while a full temperature-logger trace on top of that pack date buys a
smaller further gain under the *old* model, but a **larger** one now that cold-chain breaks
and a generative trace replace the retired truncated-normal temperature law (ADR 0150). This
page explains why duration still dominates, and why the temperature channel finally has
something real left to learn once a pack date is known.

![Duration (days) vs. mean transit temperature factor for the six real Abdella shipments used to anchor the arrival model's assumed families](/figures/cold-chain-arrival-calibration-overlay.png)

## The idea

Every delivery's freshness at arrival is driven by one number: cumulative thermal exposure
Λ (roughly "duration times average heat," plus break damage when the chain fails). Two
things could make Λ vary from one truck to the next: the trip could take a different number
of days, or the truck could run warmer or suffer cold-chain breaks. If you only get to
observe *one* of those two things, which one explains the most variation?

Measured against the six real Abdella cold-chain shipments used to anchor this model's
assumed families, **duration still swings much more than the clean-chain temperature
factor** — roughly 1.9 to 6.5 days versus a narrow φ̄ band (roughly 1.29 to 1.48 on the
overlay). A pack date pins calendar duration `d` — that's why it still buys so much
belief-sharpening for so little instrumentation.

The old story overstated how little temperature could matter *after* a pack date. Under the
retired truncated-normal sub-model (`mu_T` / `sigma_T`, now removed from the artifact),
`shipments.rs::truth_transit_trace` **fabricated** a trace and bisected a constant offset
until its φ̄ matched an already-drawn scalar — so the trace carried almost no information
beyond duration plus a temperature draw that barely moved. That produced a **98.4% / 1.6%**
split in `Var(log Λ)` between duration and φ̄. It was a measurement of six clean shipments
*and* a modelling artifact, not a universal law.

The current model (ADR 0150) makes the **path generative**: `truth_transit_trace` builds a
legged baseline, punches compound-Poisson break events into it, and Λ comes back out of the
path via `resolve_arrival_exposure` — the same integration the F3 observation channel uses.
Break severity is **duration at a fixed break temperature**, not a wider ambient draw, so
thermal uncertainty that a pack date cannot see is real again. At default break parameters
(`rho = 0.08` / day, `tau_bar = 0.5` d, `T_break = 12 °C`), the artifact provenance
documents a **~80% duration / ~20% break-thermal** share of `Var(log Λ)` — versus ~100% /
~0% at `rho = 0` on a break-free path. A pack date still removes most shipment-level
uncertainty by pinning `d`; a full temperature trace now mops up a **meaningful** residual,
not a decorative 1.6% mop-up.

## The math

Define $\Lambda = d \cdot \bar\varphi \cdot \psi$ on a break-free clean chain, or more
generally $\Lambda = d \cdot \phi_{\mathrm{set}} + \sum_j \tau_j (\phi_{\mathrm{break}} -
\phi_{\mathrm{set}})$ when breaks occur inside total calendar duration $d$ (see
[the cold-chain arrival model](/store/cold-chain-arrival) and ADR 0150). Decompose the log
of the shared, per-shipment part of exposure:

$$
\mathrm{Var}(\log \Lambda) \approx \mathrm{Var}(\log d) + \mathrm{Var}(\log \bar\varphi_{\mathrm{thermal}})
$$

(treating the dominant factors as approximately independent across shipments, and ignoring
the per-unit position term $\psi$, which is drawn independently per unit rather than
varying trip-to-trip).

**Duration (still anchored to the six shipments).** Computed directly from the Abdella
parquet over the refrigerated leg:

$$
\mathrm{Var}(\log d) = 0.205
$$

This number is a **hard calibration check** on the fitted corridor duration family — it
does not depend on the thermal sub-model.

**Thermal piece (model-dependent).** Under the old truncated-normal + decorative trace,
$\mathrm{Var}(\log \bar\varphi) = 0.00335$, giving the familiar **98.4% / 1.6%** duration
share. That split is **retired** as a guard target: it mixed a real duration measurement
with a temperature law that left almost nothing generative for F3 to observe.

Under the break-event model at default `rho`, the artifact provenance records a duration
share of **~82%** of `Var(log \Lambda)` — roughly **~80% duration / ~20% break thermal**
at the documented default parameters, a **scenario design** number, not something estimated
from six clean chains that never broke. At `rho = 0`, duration share approaches 100% on the
deterministic legged baseline.

A pack date is observationally a duration measurement (calendar days from pack to arrival,
once rounded to a whole day). Knowing it removes most of the shipment-level uncertainty in
$\Lambda$ from $d$ alone. A full temperature trace adds path detail — breaks, setpoint legs,
and (once the v2 transit plan lands) trip thermal mode and hourly noise — which is why F3
should matter more than the old 1.6% mop-up suggested, even though duration remains the
headline driver.

## Why it's modelled this way

This isn't an assumption baked into the model without measurement — the **duration**
moments come from six real Abdella shipments, and they directly shape a modeling decision:
duration is treated as an *explicit corridor input* (drawn from a fitted family per
corridor) because six shipments are nowhere near enough to *infer* a duration distribution
reliably from data alone, but they are enough to establish that duration is the dominant
source of variation worth modeling carefully.

**What changed (ADR 0150).** The retired truncated-normal draw (`mu_T`, `sigma_T`) and
decorative bisection trace are replaced by deterministic **legs** (duration-weighted
setpoints), **break events** (`rho`, `tau_bar`, `T_break`), and path integration. Break
frequency is **assumed**, not fit — all six Abdella shipments are clean chains — but break
*severity* is duration at a fixed break temperature, which is exactly the residual thermal
risk a pack date cannot see.

**Calibration guards (updated).** The old guard that required reproducing the **98.4%**
duration share at `rho \to 0` under a fully deterministic baseline was unachievable (share
→ 100%). The replacement keeps **`Var(log d) \approx 0.205`** as the hard Abdella duration
check and treats the default-`rho` duration-vs-break share as a documented modelling regime
in artifact provenance, not a measurement from six clean traces.

**Planned (not yet in code).** The transit generative v2 plan (see handoff on the integrate
branch) will restore **mild clean-chain φ̄ scatter** via trip cool/nominal/warm modes and
required hourly OU on the path — tuned to match the six shipments' φ̄ moments at `rho = 0`,
without reintroducing `mu_T` / `sigma_T`. That work is planned; Stage 1 on the integrate
branch ships deterministic legs + breaks first.

**An alternative considered.** One candidate calibration criterion required residual
variance *after* observing temperature to be smaller than residual variance after
observing duration ($\mathrm{Var}(f \mid \bar\varphi) < \mathrm{Var}(f \mid d)$). Given
the old 98.4%/1.6% split, this was backwards. Under the break model the F3 residual is
larger by design — that is the point of the redesign.

**Honest caveat.** The **0.205** duration variance and the overlay's duration-vs-φ̄ scatter
come from **six** cold-chain shipments (Abdella, Brecht & Uysal 2021), refrigerated leg
only. They are not claims about universal cold-chain physics — with six data points the
confidence interval on any split is wide, and the underlying dataset is a strawberry logger
study substituted for blueberry kinetics (see [Limitations](./limitations)). The **~80%/20%**
default-`rho` split is an assumed scenario documented in provenance, not measured from those
six traces. This is a *between-shipment* decomposition, not a within-shipment one.

## In the code

| Concept | Symbol / field | File:line |
| --- | --- | --- |
| Deterministic transit legs (break-free baseline) | `legs` | `crates/voi_core/src/arrival.rs:235` |
| Cold-chain break hazard and mean break duration | `rho`, `tau_bar`, `T_break` | `crates/voi_core/src/arrival.rs:245-248`, `:242` |
| Cumulative exposure with breaks inside calendar `d` | `lambda_from_breaks` | `crates/voi_core/src/arrival.rs:1120` |
| Generative path + integrated Λ | `draw_transit`, `truth_transit_trace` | `crates/voi_core/src/arrival.rs:1335`, `crates/voi_core/src/shipments.rs:98` |
| Q10 exposure from an observed trace (F3 channel) | `resolve_arrival_exposure` | `crates/voi_core/src/arrival.rs:2334` |
| Per-unit truth draw (duration + breaks + position) | `draw_unit_f` | `crates/voi_core/src/arrival.rs:1375` |
| Corridor duration family + break defaults | `corridors`, `rho`, `tau_bar`, `legs` | `data/abdella/arrival_model.json` |
| Abdella duration fit and provenance notes | — | `scripts/fit_abdella_arrival.py`, `data/abdella/arrival_model.json` (`provenance.adjustment_notes.breaks`) |
| Six-shipment empirical overlay (duration vs. φ̄) | — | `data/abdella/calibration_note.md`, `data/abdella/arrival_calibration_overlay.png` |

## Caveats

- **`Var(log d) = 0.205`** is measured across only **six** shipments — treat it as a strong
  directional anchor, not a precisely-known population parameter.
- The **~80%/20%** default-`rho` split is a **documented modelling regime** in artifact
  provenance, not an empirical measurement from those six clean chains.
- The decomposition is between-shipment (why do trips differ from each other), not
  within-shipment (how much does temperature matter to any one trip's outcome).
- The underlying transit dataset is a strawberry cold-chain logger study, not a
  blueberry-specific one; see [Limitations](./limitations).
- Clean-chain **φ̄ mode/OU scatter** from the v2 transit plan is **planned, not yet shipped**
  — until then, mild thermal variation on break-free paths comes from setpoint legs only.
- This explains why *duration* observations (pack date) help so much and why *temperature*
  observations should help **more than before** once breaks are generative — it does not by
  itself explain why waste totals fail to help; see
  [Does belief actually sharpen?](./does-belief-sharpen)
