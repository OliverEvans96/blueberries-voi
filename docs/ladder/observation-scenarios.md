---
title: The observation ladder
sources:
  code:
    - crates/voi_core/src/obs.rs
    - web/src/obsMask.ts
  adr: ["0149", "0150", "0133"]
---

# The observation ladder

The [observation grid](./channels.md) has 12 reachable combinations in total, but most of
the project's charts, tests, and Value of Information (VOI) sweeps walk a single path
through it: a five-rung ladder, where each rung adds one piece of real-world
instrumentation a grocer could actually buy. That five-rung path is the main story on this
page. A couple of extra presets exist for readers who want the full 12-combination grid —
those are covered near the end, clearly marked as bonus material.

## The idea

Reading down the ladder, each rung adds one thing a real store could buy or change: a
handheld scanner, a barcode format that carries lot identity, pack dates in a supplier's
paperwork, or temperature loggers riding along in the truck. None of these devices
measures freshness directly — they only change what shows up in the daily record, and the
model (the "filter") does all the work of turning that record into a belief about how
fresh the berries actually are.

Here's the ladder, in order:

| Rung | What's newly tracked |
| --- | --- |
| **Books only** | What nearly every store already has: a point of sale (POS) system and a receiving log, so you know how many units were delivered and how many were sold. Waste totals aren't part of this rung — those show up next. |
| **+ scan waste** | A handheld scanner adds a daily count of how many units were thrown out storewide. |
| **+ pack date** | The supplier starts printing pack dates on the Advance Ship Notice (ASN) — the paperwork that precedes a delivery — so the model learns roughly how long each shipment spent in transit. |
| **+ LGTIN** | Checkout switches from a plain Universal Product Code (UPC), which identifies only the product, to an LGTIN — a Global Trade Item Number (GTIN) plus a batch/lot number, which can tell one truckload of a product apart from another. Waste counts and pack dates can now be tied to a specific lot instead of pooled across every lot in a delivery. |
| **+ temp. history** | The truck also logs temperature along the route, so the model can see cold-chain problems — a stop, a door left open — directly, instead of inferring them indirectly from transit duration alone. |

What does each rung actually buy? Two measures matter here: how far off the model's
freshness belief is from the simulator's true state (lower is better, shown as a ratio to
the books-only baseline), and how much profit the store's ordering rule earns using that
belief (also shown as a ratio to books-only). Across a 30-day replay over 30 random seeds:

| Rung | Belief error ratio vs. books-only | Profit ratio vs. books-only |
| --- | --- | --- |
| Books only | 1.000 (baseline) | 1.000 (baseline) |
| + scan waste | 1.036 ± 0.026 | 1.009 ± 0.008 |
| + pack date | 0.453 ± 0.048 | 1.003 ± 0.015 |
| + LGTIN | 0.301 ± 0.019 | 1.004 ± 0.014 |
| + temp. history | 0.214 ± 0.013 | 1.006 ± 0.014 |

Two conclusions stand out:

- **Belief accuracy improves steadily as you climb the ladder, and pack date is the single
  biggest jump.** Just knowing pack dates — with checkout still reading plain UPCs — cuts
  the belief-error ratio from 1.036 down to 0.453, more than halving it. Adding LGTIN and
  then temperature history keep sharpening the belief further, down to about 0.301 and
  then about 0.214, but neither step is as large as the pack-date jump.
- **Profit barely moves.** Even though the belief keeps getting sharper, the store's
  ordering rule earns profit within about 1% of the books-only baseline at every rung.
  Sharper information doesn't translate into more profit in this experiment — see
  [Why it's modelled this way](#why-its-modelled-this-way) for the likely reason.

## The math

Each observation scenario is a fixed point $(c, w, h)$ in the grid described in
[Channels](./channels.md): $c$ is the checkout code type (UPC or LGTIN), $w$ is whether
waste gets scanned (yes or no), and $h$ is what delivery history is available (none, pack
date, or full temperature history). The code exposes this as a lookup from a scenario name
to its channel triple, plus the reverse lookup, which only returns a plain scenario name
when the channel triple exactly matches one of the ladder rungs or one of the bonus
presets below — any other combination is reported as "custom" rather than being forced
into a nearest-scenario label.

## Why it's modelled this way

The named presets exist so that Value of Information (VOI) sweeps and charts can be keyed
by a short, memorable name instead of a raw channel triple. The five rungs are chosen to
track a real adoption story: cheap process changes first — a scanner, a supplier printing
dates — and capital purchases later, like new barcode hardware or temperature loggers.
That's why the ladder above reads as a sequence of purchasing decisions, not just rows in
a truth table.

Why does profit barely move even as belief gets sharper? The likely reason is that the
store's ordering rule is short-sighted: it only plans around current average freshness and
demand until the next delivery arrives, a few days out, not the blueberries' full shelf
life of roughly ten days. So it can't fully exploit a sharper belief about freshness
further out. The economics reinforce this: missing a sale costs roughly $5.20 (a $2.50
stockout penalty plus the $2.70 margin you forgo), against $1.20 to waste a spoiled unit —
about 4.3 times as expensive. A policy that already leans toward over-ordering to avoid
that steep stockout cost ends up close to profit-maximizing even with a coarse belief.
Two other ordering-rule designs were tried, and neither improved profit meaningfully
either, which points at the ordering rule rather than the extra information as the
limiting factor.

**Additional detail for readers who want the full 12-combination grid.** Two extra presets
sit off the main ladder. Both use LGTIN at checkout with no delivery history at all
(code_type = LGTIN, scan_waste = yes, delivery_history = none). One is labeled "Lot ID at
POS"; the other, "Lot ID on the waste scanner." They're meant to describe two different
instruments. "Lot ID at POS" reads lot codes at checkout, with storewide waste counts.
"Lot ID on the waste scanner" reads plain UPCs at checkout but reads lot codes on the
waste-scanning device instead, giving per-lot waste counts with no change to the register.
Because waste granularity in the current model is derived from the same switch that
controls the checkout code type (see [Channels](./channels.md)), the model can't actually
produce that second combination — a store can't get per-lot waste without also reading lot
codes at checkout. The code's preset lookup reflects this directly: both preset names map
to the identical channel triple, and a check confirms the two resulting masks are equal.
"Lot ID on the waste scanner" still appears in the UI and in VOI sweeps as a distinct
label, but today it teaches nothing that "Lot ID at POS" doesn't.

## In the code

| Observation scenario | Channels (code_type, scan_waste, delivery_history) | Business translation | File:line |
| --- | --- | --- | --- |
| **Books only** | upc, off, none | Nothing beyond ordinary POS and receiving — no new purchase. | `crates/voi_core/src/obs.rs:194` |
| **+ scan waste** | upc, on, none | Buy a handheld scanner for daily storewide waste counts; no barcode change. | `crates/voi_core/src/obs.rs:199` |
| **+ pack date** | upc, on, pack_date | Get the supplier to print/transmit pack dates on the ASN; register still reads pooled UPC codes. | `crates/voi_core/src/obs.rs:209` |
| **+ LGTIN** | lgtin, on, pack_date | Switch checkout to lot-resolved (LGTIN) codes; waste and pack-date data now tie to individual lots. | `crates/voi_core/src/obs.rs:214` |
| **+ temp. history** | lgtin, on, temperature_history | Add per-lot temperature traces on top of the LGTIN rung, pinning cold-chain exposure directly. | `crates/voi_core/src/obs.rs:219` |
| Lot ID at POS (bonus preset, internally "F1") | lgtin, on, none | Switch checkout to lot-resolved codes with no delivery-history channel at all. | `crates/voi_core/src/obs.rs:204` |
| Lot ID on the waste scanner (bonus preset; identical mask to "Lot ID at POS" — see caveat above) | lgtin, on, none | Intended design: keep UPC at checkout, put lot-resolved codes only on the waste-scanning device. Not separately representable in the current code. | `crates/voi_core/src/obs.rs:204` |
| Preset table (TypeScript mirror) | `PRESET_CHANNELS` | Studio UI reads the same set of named presets. | `web/src/obsMask.ts:69` |
| Round-trip check covering every named preset | `preset_round_trip_matches_mask_for` | | `crates/voi_core/src/obs.rs:512` |
| "Lot ID on the waste scanner" ≡ "Lot ID at POS" check | `mask_for_f1s_matches_f1` | | `crates/voi_core/src/obs.rs:582` |
| Pack-date-only mask check | `mask_for_f2a_is_p1_plus_pack_date` | | `crates/voi_core/src/obs.rs:587` |
| LGTIN + pack-date mask check | `mask_for_f2_has_maps_and_pack_date` | | `crates/voi_core/src/obs.rs:595` |
| Temperature-history passthrough check | `apply_f3_passes_shipment_trace` | | `crates/voi_core/src/obs.rs:639` |
| Regression check that belief error gets worse, not better, moving from the richest scenario down to books-only | `ac2_11a_empirical_ladder_tracking_mae` | | `crates/voi_core/tests/t150_phase2_arrival_model.rs` |

## Caveats

The "business translation" column above is illustrative narrative, not something the code
enforces or prices — the model has no cost field for a waste scanner or a temperature
logger. The scenario names also don't imply that every metric always improves in lockstep.
[No channel observes freshness](./no-channel-observes-freshness.md) explains why richer
scenarios sharpen belief in a specific, checkable sense — a narrower distribution over
freshness — rather than "more data always better" in some vague sense.

As covered above, "Lot ID on the waste scanner" is presently a relabeling of "Lot ID at
POS," not an independent instrument. Readers comparing results between the two anywhere in
this project should expect no difference; that's expected behavior of the current model,
not a bug in the comparison.

Belief accuracy on this ladder is tracked with Mean Absolute Error (MAE) on the model's
average freshness estimate, plus the 1-Wasserstein distance (W1) — a measure of how far
apart two distributions are — on the full freshness distribution, since MAE alone can hide
a belief that has the right average but the wrong shape. Where a full predictive
distribution over unit counts is available, the Continuous Ranked Probability Score (CRPS)
is used too, since it checks the whole predicted distribution against what actually
happened, not just its mean. A regression check (see the In-the-code table) keeps the
ladder honest by asserting that belief error strictly gets worse moving from the richest
scenario down to books-only.
