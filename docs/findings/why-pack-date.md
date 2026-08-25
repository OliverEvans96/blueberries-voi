---
title: Why a pack date does so much
sources:
  code:
    - crates/voi_core/src/arrival.rs
    - data/abdella/arrival_model.json
    - data/abdella/calibration_note.md
    - scripts/arrival_calibration_note.py
---

# Why a pack date does so much

[The previous finding](./does-belief-sharpen) showed that adding a supplier pack date to
the delivery record cuts belief error roughly 3× — the largest single step on the whole
knowledge ladder — while a full temperature-logger trace on top of that pack date buys a
much smaller further gain. This page explains why: almost all of the trip-to-trip
variation in cumulative thermal exposure comes from how long the trip took, not from how
warm it ran.

![Duration (days) vs. mean transit temperature factor for the six real Abdella shipments used to anchor the arrival model's assumed families](/figures/cold-chain-arrival-calibration-overlay.png)

## The idea

Every delivery's freshness at arrival is driven by one number: cumulative thermal exposure
`Lambda` (Λ), roughly "duration times average heat." Two things could make Λ vary from one
truck to the next: the trip could take a different number of days, or the truck could run
at a different average temperature. If you only get to observe *one* of those two things,
which one explains the most variation?

Measured against the six real Abdella cold-chain shipments used to anchor this model's
assumed families, the answer isn't close. Duration swings by more than 3× across the six
trips (roughly 1.9 to 6.5 days); the temperature factor barely moves (roughly 1.29 to
1.48). Almost all of the shipment-to-shipment spread in Λ traces back to how long the
truck was on the road, not to how the reefer was running while it drove. A pack date pins
down duration — that's why it buys so much belief-sharpening for so little
instrumentation.

## The math

Define $\Lambda = d \cdot \bar\varphi \cdot \psi$ (see
[the cold-chain arrival model](/store/cold-chain-arrival) for the full generative story),
where $d$ is calendar transit duration in days and $\bar\varphi$ is the duration-averaged
Q10 temperature factor. Decompose the log of the shared, per-shipment part of exposure:

$$
\mathrm{Var}(\log \Lambda) \approx \mathrm{Var}(\log d) + \mathrm{Var}(\log \bar\varphi)
$$

(treating $d$ and $\bar\varphi$ as approximately independent across shipments, and
ignoring the per-unit position term $\psi$, which is drawn independently per unit rather
than varying trip-to-trip). Computed directly from the six-shipment Abdella parquet:

$$
\mathrm{Var}(\log d) = 0.205, \qquad \mathrm{Var}(\log \bar\varphi) = 0.00335
$$

which gives a duration share of

$$
\frac{\mathrm{Var}(\log d)}{\mathrm{Var}(\log d) + \mathrm{Var}(\log \bar\varphi)} \approx 98.4\%.
$$

Duration accounts for roughly 98.4% of the between-shipment variance in log cumulative
exposure; the temperature factor accounts for the remaining ≈1.6%. A pack date is
observationally a duration measurement (calendar days from pack to arrival, once rounded
to a whole day) — nothing more — so knowing it removes most of the shipment-level
uncertainty in $\Lambda$ before the filter does anything else. A full temperature trace
adds $\bar\varphi$ (and de-rounds $d$ to its exact value), which is why the full
temperature-history scenario still helps, but it only mops up what's left after duration
is already known.

## Why it's modelled this way

This isn't an assumption baked into the model — it's a measurement from the six real
Abdella shipments, and it directly shapes a modeling decision: duration is treated as an
*explicit corridor input* (drawn from a fitted family per corridor) because six shipments
are nowhere near enough to *infer* a duration distribution reliably from data alone, but
they are enough to establish that duration, not temperature, is the dominant source of
variation worth modeling carefully.

**An alternative considered.** One candidate calibration criterion required residual
variance *after* observing temperature to be smaller than residual variance after
observing duration ($\mathrm{Var}(f \mid \bar\varphi) < \mathrm{Var}(f \mid d)$). Given
the 98.4%/1.6% split above, this is backwards: requiring temperature to explain more of
the *remaining* uncertainty than duration does requires duration to contribute *less*
variance overall — the opposite of what the data show. A parameter set satisfying that
inverted criterion gave duration a mere 23% share of $\mathrm{Var}(\log \Lambda)$. The
calibration guard actually used instead pins the model's duration share to within a band
of the observed 98.4%, computed directly from the parquet rather than asserted.

**Honest caveat.** This is a between-shipment decomposition from **six** cold-chain
shipments (Abdella, Brecht & Uysal 2021), refrigerated leg only. It is not a claim that
98.4%/1.6% is a universal physical constant of blueberry cold chains — with six data
points the confidence interval on that split is wide, and the underlying dataset is a
strawberry logger study substituted for blueberry kinetics (see
[Limitations](./limitations)). It is also a *between-shipment* decomposition, not a
within-shipment one: it says duration is what varies most from trip to trip, not that
temperature is unimportant to any single trip's outcome.

## In the code

| Concept | Symbol / field | File:line |
| --- | --- | --- |
| Cumulative thermal exposure | $\Lambda = d \cdot \bar\varphi \cdot \psi$ | `crates/voi_core/src/arrival.rs:464` ([`draw_unit_f`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.draw_unit_f)) |
| Duration draw (shifted gamma, per corridor) | $d = d_{\min} + \mathrm{Gamma}(\text{delay\_shape}, \text{delay\_scale})$ | `crates/voi_core/src/arrival.rs:375-377` |
| Duration-averaged Q10 temperature factor | $\bar\varphi = q_{10}^{(\bar T - T_\mathrm{ref})/10}$ | `crates/voi_core/src/arrival.rs:366` ([`phi_bar_from_t_bar`](/api/rust/voi_core/arrival/struct.ArrivalModel.html#method.phi_bar_from_t_bar)) |
| Corridor duration/temperature parameters, fitted per corridor | `d_min`, `delay_shape`, `delay_scale`, `mu_T`, `sigma_T` | `data/abdella/arrival_model.json` |
| Duration-share calibration guard (≥90% against observed 98.4%) | — | `scripts/arrival_calibration_note.py` |
| Six-shipment empirical overlay (duration vs. temperature factor) | — | `data/abdella/calibration_note.md`, `data/abdella/arrival_calibration_overlay.png` |

## Caveats

- The 98.4%/1.6% split is measured across only **six** shipments — treat it as a strong
  directional signal from the available data, not a precisely-known population parameter.
- The decomposition is between-shipment (why do trips differ from each other), not
  within-shipment (how much does temperature matter to any one trip's outcome) — both are
  true and both matter, but they answer different questions.
- The underlying transit dataset is a strawberry cold-chain logger study, not a
  blueberry-specific one; see [Limitations](./limitations) for why that substitution was
  made and what it means for how much to trust the absolute numbers.
- This explains why *duration* observations (pack date) help so much and *temperature*
  observations add comparatively little on top — it does not by itself explain why waste
  totals (the "shrink gun" scenario) fail to help at all; that's a separate finding,
  covered in [Does belief actually sharpen?](./does-belief-sharpen)
