---
title: The seven named observation scenarios
sources:
  code:
    - crates/voi_core/src/obs.rs
    - web/src/obsMask.ts
  adr: ["0149", "0150", "0133"]
---

# The seven named observation scenarios

The [observation grid](./channels.md) has 12 reachable combinations, but most of the
project's charts, tests, and VOI sweeps refer to just seven named points on it. These are
**presets**, not separate models — each one is a fixed choice of the same three channel
switches, kept as a named shorthand because they trace a plausible investment path a real
grocer would walk, cheapest first.

## The idea

Reading down the table below, each scenario adds one piece of real-world instrumentation.
The baseline scenario assumes nothing beyond what every grocery store already has (a
point-of-sale system and a receiving log). Every scenario after that corresponds to a
purchase or a process change: a handheld scanner, a barcode format that carries lot
identity, pack dates on a supplier's paperwork, loggers that ride in the truck. None of
these devices measures freshness — they only change what shows up in the daily
observation log, and the filter has to do all the work of turning that log into a belief
about freshness.

After ADR 0149 and ADR 0150, what each step buys is sharper than under the old
single-cohort arrival story:

| Scenario | What it buys with $L = 3$ lots and break-event transit |
| --- | --- |
| **Books only** (P0) | Pooled sales and arrival counts only. Truth always births three shelf segments; the filter still models one merged cohort — a fixed, knowable cardinality misspecification. |
| **Shrink gun** (P1) | Storewide waste totals. Still no delivery journey or lot identity; waste helps score spoilage but cannot split three coexisting segments. |
| **Lot ID at POS** (F1) | Per-lot sales, waste, and arrival lot ids. Opens sequential attribution, composition (how $Q$ split across three lots), and lot-count information LGTIN can express but UPC cannot. |
| **Pack date on the ASN** (F2a) | Pins transit duration for the delivery, but under UPC the three per-lot pack dates on the ASN are mixed into one birth law — duration information without per-lot segmentation. |
| **Lot ID + pack date** (F2) | Same pack-date paperwork, but LGTIN holds three segments each born from its own duration draw — separates lots that share a truck yet took different upstream journeys. |
| **Lot ID + pack date + temperature history** (F3) | Full per-lot exposure traces under ADR 0150's break-event model. Mops up thermal exposure variance the pack date leaves behind — a much larger step than when the trace was decorative. |

The **F2a → F2** gap is the cleanest place to see ADR 0149's structural fork: identical
supplier paperwork, different register resolution. Under the pre-0149 ladder that step
was nearly flat (measured MAE 0.034 vs 0.032) because lot identity was redundant with
shelf tenure; with three fixed lots it is expected to widen.

The **F2 → F3** step is also larger post-0150. Cold-chain break events replace the old
transit-temperature sub-model, so a temperature trace pins cumulative exposure $\Lambda$
with meaningful between-shipment spread rather than bisecting a nearly fixed mean
temperature. Duration still dominates, but the residual exposure variance a trace can
remove is no longer negligible.

## The math

Each observation scenario is a fixed point $(c, w, h)$ in the grid from
[Channels](./channels.md). The code exposes this as a lookup from a scenario id to its
channel triple, and its inverse, which returns a scenario name only when the channel
triple exactly matches one of the seven presets — any other combination reports as
"custom" rather than forcing a nearest-scenario label.

## Why it's modelled this way

The named presets exist so that value-of-information sweeps and charts can be keyed by a
short scenario id rather than a raw channel triple. The seven scenarios are also chosen
to track a real adoption story — cheap process changes first, capital purchases later —
which is why this page frames each row as a purchasing decision rather than just a row in
a truth table.

**Caveat — two scenarios currently collapse to the same channel triple.** "Lot ID at POS"
and "Lot ID on the shrink gun" describe two different instruments: the former reads lot
codes at checkout with storewide waste counts, while the latter reads plain UPCs at
checkout but reads lot codes on the *waste* gun, giving per-lot waste with no change to
the register. Because waste granularity is derived from the POS code-type switch (see
[Channels](./channels.md)), the current model cannot produce that second combination — a
store cannot get per-lot waste without also reading lot codes at POS. The code's preset
lookup reflects this directly: it maps both scenario ids to the identical channel triple,
and a dedicated test asserts the two resulting masks are equal. "Lot ID on the shrink gun"
survives in the UI and in VOI sweeps as a distinct label, but it currently teaches nothing
that "Lot ID at POS" does not.

## In the code

| Observation scenario | Channels (code_type, scan_waste, delivery_history) | Business translation | File:line |
| --- | --- | --- | --- |
| **Books only** | upc, off, none | Nothing beyond ordinary POS and receiving — no new purchase. | `crates/voi_core/src/obs.rs:194` |
| **Shrink gun** | upc, on, none | Buy a handheld scanner for daily storewide waste counts; no barcode change. | `crates/voi_core/src/obs.rs:199` |
| **Lot ID at POS** | lgtin, on, none | Switch checkout to lot-resolved (LGTIN) codes; waste counts come back per lot as a side effect. | `crates/voi_core/src/obs.rs:204` |
| **Lot ID on the shrink gun** | lgtin, on, none *(identical to "Lot ID at POS" — see caveat above)* | Intended design: keep UPC at checkout, put lot-resolved codes only on the waste gun. Not separately representable in the current code. | `crates/voi_core/src/obs.rs:204` |
| **Pack date on the ASN** | upc, on, pack_date | Get the supplier to print/transmit pack dates on the ASN; register still reads pooled UPC — three dates mix into one birth law. | `crates/voi_core/src/obs.rs:209` |
| **Lot ID + pack date** | lgtin, on, pack_date | Lot-resolved POS plus per-lot duration conditioning on three shelf segments. | `crates/voi_core/src/obs.rs:214` |
| **Lot ID + pack date + temperature history** | lgtin, on, temperature_history | F2 plus per-lot temperature traces that pin exposure under break-event transit. | `crates/voi_core/src/obs.rs:219` |
| Preset table (TS mirror) | `PRESET_CHANNELS` | Studio UI reads the same seven presets. | `web/src/obsMask.ts:69` |
| Round-trip test (all 7 presets) | `preset_round_trip_matches_mask_for` | | `crates/voi_core/src/obs.rs:512` |
| "Lot ID on the shrink gun" ≡ "Lot ID at POS" assertion | `mask_for_f1s_matches_f1` | | `crates/voi_core/src/obs.rs:582` |
| F2a mask (UPC + pack date, no lot maps) | `mask_for_f2a_is_p1_plus_pack_date` | | `crates/voi_core/src/obs.rs:587` |
| F2 mask (LGTIN maps + pack date) | `mask_for_f2_has_maps_and_pack_date` | | `crates/voi_core/src/obs.rs:595` |
| F3 passes trace through mask | `apply_f3_passes_shipment_trace` | | `crates/voi_core/src/obs.rs:639` |

## Caveats

The "business translation" column is illustrative narrative, not something the code
enforces or prices — the model has no cost field for a shrink gun or a temperature
logger. The scenario names also do not imply a strict information ordering on every
metric; [No channel observes freshness](./no-channel-observes-freshness.md) explains why
richer scenarios sharpen belief in a specific, checkable sense (a narrower distribution
over freshness) rather than "more data always better" in some vague sense. And as covered
above, "Lot ID on the shrink gun" is presently a relabeling of "Lot ID at POS," not an
independent instrument — readers comparing results between the two anywhere in this
project should expect no difference, and that is expected behavior of the current code,
not a bug in the comparison.

Measured MAE numbers on this ladder drift when the arrival generative story changes —
re-run `notebooks/article_figures.ipynb` after multi-lot and break
wiring land. The ordering guard
`crates/voi_core/tests/t150_phase2_arrival_model.rs::ac2_11a_empirical_ladder_tracking_mae`
is the regression anchor: shelf-mean freshness MAE must strictly increase from F3 down to
P0. Shape-aware scores used elsewhere ($W_1$ on live freshness; CRPS on count when a
particle predictive is available) are complementary; the studio's belief-accuracy table
reports mean-f MAE plus freshness $W_1$ (All-days = mean of daily $W_1$).
