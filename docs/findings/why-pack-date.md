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
the delivery record cuts belief error by more than half — the single biggest jump on the
observation ladder. A full temperature-logger trace on top of that pack date used to buy
only a small further gain, but it buys a **larger** one now: the model simulates cold-chain
breaks directly instead of faking a temperature trace to match a number drawn elsewhere.
This page explains why trip duration still dominates, and why the temperature-history
scenario finally has something real left to learn once a pack date is already known.

## The idea

Every delivery's freshness at arrival comes down to one number: cumulative thermal
exposure, written Λ (Lambda) — roughly "how long the trip took, times how warm it ran,"
plus extra damage from any cold-chain breaks along the way. Two things can make Λ differ
from one truck to the next: the trip can take a different number of days, or the truck can
run warmer, or worse, suffer a cold-chain break (a stop, a door left open). If you could
only observe *one* of those two things — duration or temperature — which one would tell
you more?

Measured against six real refrigerated shipments used to calibrate this model's timing
assumptions, **duration swings far more than temperature does on a clean run** — trip
length ranges roughly 1.9 to 6.5 days, while the clean-chain temperature factor stays in a
narrow band (roughly 1.29 to 1.48). A pack date pins down calendar duration exactly —
that's why knowing it buys so much belief-sharpening for so little extra instrumentation.

The older version of this model understated how much temperature could still matter once
duration was known. It worked by drawing a temperature summary number first, then building
a fake trace that was bent to match it — so the trace itself carried almost no information
beyond "duration, plus a temperature draw that barely moved." That produced a **98.4% /
1.6%** split of the shipment-to-shipment variance between duration and temperature. That
split was really a fact about six clean shipments *and* an artifact of how the old model
was built, not a universal law about cold chains.

The current model instead simulates the whole trip leg by leg, including realistic
cold-chain break events — a process where disruptions like a door left open arrive randomly
and can cluster together — and reads the thermal exposure back out of that simulated path.
Break severity is modeled as *extra time spent at a fixed, higher break temperature*, not
just a wider random guess at ambient temperature, so the thermal uncertainty that a pack
date alone can't see is real again. At the model's default break settings, a full
temperature trace now mops up a **meaningful** share of the remaining uncertainty, not the
old model's decorative 1.6%.

## The math

The two things driving shipment-to-shipment variation — trip duration and the thermal
path — can be split apart the same way you'd split any two contributing causes: by looking
at how much each one's variance contributes to the total. On a clean chain (no breaks),
exposure is duration times an average temperature factor times a small per-unit noise term:
$\Lambda = d \cdot \bar\varphi \cdot \psi$, where $d$ is trip duration in days, $\bar\varphi$
is the average temperature factor over the trip, and $\psi$ is inter-lot position noise —
each unit in a shipment doesn't experience quite the same conditions, so its own freshness
wobbles a little around the shipment average (this matches the model's default inter-lot
noise setting, sigma_pos = 0.08). More generally, once cold-chain breaks are allowed,
exposure adds up the normal running time plus any break time at a warmer temperature:
$\Lambda = d \cdot \phi_{\mathrm{set}} + \sum_j \tau_j (\phi_{\mathrm{break}} -
\phi_{\mathrm{set}})$, where $\phi_{\mathrm{set}}$ is the temperature factor while running
normally, $\tau_j$ is how long break $j$ lasted, and $\phi_{\mathrm{break}}$ is the
temperature factor during a break (see [the cold-chain arrival model](/store/cold-chain-arrival)
for the full derivation). Splitting the variance of log exposure into its two shipment-level
sources, and setting aside the per-unit noise term above (it varies unit to unit, not trip
to trip):

$$
\mathrm{Var}(\log \Lambda) \approx \mathrm{Var}(\log d) + \mathrm{Var}(\log \bar\varphi_{\mathrm{thermal}})
$$

**Duration, measured directly from the six calibration shipments:**

$$
\mathrm{Var}(\log d) = 0.205
$$

This number is a hard calibration check on the fitted trip-duration assumptions — it
doesn't depend on which thermal model is used.

**The thermal piece is model-dependent.** Under the old, retired temperature model, the
thermal variance was tiny (giving that familiar 98.4% / 1.6% duration-vs-temperature
split). That split has been retired as a target: it mixed a real duration measurement with
a temperature model that left almost nothing for a temperature trace to observe.

Under the current break-event model, at its default settings, duration accounts for
roughly **~80%** of the shipment-to-shipment variance and cold-chain breaks account for the
other **~20%** — a deliberate scenario design choice documented alongside the model, not a
number measured from six shipments that happened never to break. With breaks turned off
entirely, duration's share climbs back toward 100%, as on the old deterministic baseline.

A pack date is, in effect, a duration measurement: the calendar days between packing and
arrival, rounded to a whole day. Knowing it removes most of the shipment-level uncertainty
that comes from duration alone. A full temperature trace adds real path detail on top —
setpoint legs and break events — which is why the temperature-history scenario should now
matter more than the old model's 1.6% suggested, even though duration remains the headline
driver. A more detailed transit model with graded trip conditions is a planned future
refinement.

## Why it's modelled this way

The duration numbers above come from measuring six real refrigerated shipments, and that
measurement directly shapes a modeling choice: duration is treated as an *explicit input*
drawn from a fitted family per corridor (the shipping-route / transit-assumption profile a
delivery uses), rather than something the model tries to infer from scratch. Six shipments
aren't enough to reliably fit a full duration distribution from data alone, but they are
enough to show that duration is the dominant source of variation and deserves to be
modeled carefully.

**What changed.** The old approach drew a single temperature summary number first, then
built a trace bent to match it after the fact — so the trace added almost no information of
its own. The current model instead builds a realistic leg-by-leg trip path and layers
break events onto it, so thermal exposure is a genuine output of the simulated path rather
than a number worked backward from a draw. Break frequency is still an assumption, not
something fit to data (all six calibration shipments happened to be clean chains with no
breaks) — but break severity is modeled as extra time at a fixed, elevated temperature,
which is exactly the kind of residual thermal risk a pack date alone can't reveal.

**Calibration checks.** The old check required reproducing the 98.4% duration share once
breaks were turned off — but that's mathematically impossible under the new model (the
share approaches 100% instead). The replacement check keeps $\mathrm{Var}(\log d) \approx
0.205$ as the hard calibration target from the six real shipments, and treats the ~80%/20%
duration-vs-break split at default settings as a documented design choice, not a
measurement.

**An alternative considered.** One idea was to require that observing temperature explain
more of the remaining uncertainty than observing duration does. Under the old model's
98.4%/1.6% split that requirement was backwards — temperature barely helped at all. Under
the current break-event model, the residual left for a temperature trace to explain is
larger by design, which is the whole point of the redesign.

**Honest caveat.** The 0.205 duration variance and the duration-vs-temperature comparison
above come from just six cold-chain shipments (Abdella, Brecht & Uysal 2021), refrigerated
leg only. They aren't claims about universal cold-chain physics — with six data points, the
uncertainty around any split is wide, and the underlying dataset is a strawberry logger
study substituted for blueberry behavior (see [Limitations](./limitations)). The ~80%/20%
default-break split is an assumed scenario design, not something measured from those six
shipments. This is also a comparison *across* shipments — how much trips differ from each
other — not a statement about how much temperature matters within any single trip.

## In the code

| Concept | Symbol / field | File:line |
| --- | --- | --- |
| Deterministic transit legs (break-free baseline) | `legs` | `crates/voi_core/src/arrival.rs:233-235` |
| Cold-chain break hazard and mean break duration | `rho`, `tau_bar`, `T_break` | `crates/voi_core/src/arrival.rs:240-248` |
| Cumulative exposure when breaks occur within the trip | `lambda_from_breaks` | `crates/voi_core/src/arrival.rs:1115-1124` |
| Simulates the trip leg-by-leg and derives exposure from it | `draw_transit`, `truth_transit_trace` | `crates/voi_core/src/arrival.rs:1335-1342`, `crates/voi_core/src/shipments.rs:97-102` |
| Spoilage-rate conversion from an observed temperature trace (the temperature-history scenario) | `resolve_arrival_exposure` | `crates/voi_core/src/arrival.rs:2334` |
| Per-unit truth draw (duration + breaks + position noise) | `draw_unit_f` | `crates/voi_core/src/arrival.rs:1375` |
| Corridor duration family and break defaults | `corridors`, `rho`, `tau_bar`, `legs` | `data/abdella/arrival_model.json` |
| Duration fit and provenance notes for the six calibration shipments | — | `scripts/fit_abdella_arrival.py`, `data/abdella/arrival_model.json` (`provenance.adjustment_notes.breaks`) |
| Six-shipment empirical overlay (duration vs. temperature) | — | `data/abdella/calibration_note.md`, `data/abdella/arrival_calibration_overlay.png` |

## Caveats

- `Var(log d) = 0.205` is measured across only six shipments — treat it as a strong
  directional signal, not a precisely-known population parameter.
- The ~80%/20% default-break split is a documented modeling choice, not an empirical
  measurement from those six clean shipments.
- The comparison is between shipments (why do trips differ from each other), not within a
  single shipment (how much temperature matters to any one trip's outcome).
- The underlying transit dataset is a strawberry cold-chain logger study, not a
  blueberry-specific one; see [Limitations](./limitations).
- A more detailed transit model with graded trip conditions is a planned future
  refinement — until then, mild thermal variation on break-free paths comes from the
  fixed setpoint legs only.
- This explains why duration observations (pack date) help so much, and why temperature
  observations should help more than before now that breaks are simulated realistically —
  it doesn't by itself explain why waste totals fail to help; see
  [Does belief actually sharpen?](./does-belief-sharpen)
