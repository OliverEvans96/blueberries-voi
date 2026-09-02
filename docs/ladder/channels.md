---
title: Observation channels
sources:
  code:
    - crates/voi_core/src/obs.rs
    - web/src/obsMask.ts
    - src/blueberries_voi/filter/types.py
  adr: ["0149", "0150", "0133"]
---

# What a store can actually see

Every belief the filter holds is built from three separate choices about what the
store *instruments*: what code gets scanned at the register, whether waste gets scanned
at all, and what the supplier tells you about a shipment's journey. Nothing else feeds
the model — there's no fourth channel, and no way to observe freshness directly.

These three choices combine into a grid of 12 possible setups. Most readers only need
the main path through that grid: the 5-rung ladder covered on the
[Observation scenarios](./observation-scenarios.md) page — books only, plus scan waste,
plus pack date, plus LGTIN, plus temperature history. This page explains where those
five points come from, plus a few extra setups that fill out the rest of the grid for
readers who want the full picture.

## The idea

Think of a grocer choosing hardware and process. There are three independent switches:

1. **What code does the register read?** A plain Universal Product Code (UPC) — the
   same barcode for every unit of a product, so the register can't tell one delivery
   from another — or a lot-resolved code called an LGTIN. An LGTIN combines a product's
   Global Trade Item Number (GTIN, the code that identifies the product itself) with a
   batch or lot number, so it can tell one truckload of a product apart from another
   truckload of the same product, not just one product from another.
2. **Does anyone scan waste?** Off — spoiled units are simply thrown out and never
   counted — or on: a handheld scanner scans culled units, producing daily counts. This
   page calls that "waste scanning."
3. **What does the supplier tell you about the shipment's journey?** Nothing beyond
   quantity, pack dates on the delivery paperwork (the Advance Ship Notice, or ASN), or
   full temperature-history traces from loggers that rode with the pallet.

Each switch is independent of the other two. A store could read lot-resolved codes at
the point of sale (POS) with a temperature-logged pallet but no waste scanning at all,
and the model handles that combination the same way it handles any point on the ladder.
That's the point of the design: it shows what each *kind* of instrument buys you,
instead of bundling everything into a handful of fixed packages.

Each delivery is modeled as three separate lots, so the filter can tell lot-to-lot
variation apart from unit-to-unit variation within one delivery — the total case
quantity is split across those three lots, not tripled. That choice changes what LGTIN
buys you. With everything pooled into a single shelf batch, knowing which lot a unit
came from was nearly redundant with how long that unit had already sat on the shelf:
time on the shelf almost fully determined how likely a unit was to sell next, so LGTIN
added almost nothing beyond a pack date. With three lots coexisting from the same
truck, lot identity now separates three things a single pooled batch can't show: how
many units sit in each lot, which lot the day's sales actually drained, and whether the
shelf still holds three distinguishable batches. LGTIN becomes meaningful again because
none of those three things can be recovered from pooled totals alone.

## The math

The three switches together form a small menu of setups, and it helps to see just how
big that menu is. Call the code-type switch $c$ (it takes the value $\text{upc}$ or
$\text{lgtin}$), the waste-scan switch $w$ (off or on), and the delivery-history switch
$h$ (none, pack date, or temperature history). Multiplying the number of choices for
each switch gives the full space of possible stores:

$$
|c| \times |w| \times |h| = 2 \times 2 \times 3 = 12 \text{ combinations.}
$$

That's why the 5-rung ladder only walks through 5 of these 12 setups: it's the most
informative path through the grid, picked to teach one new thing at a time, not a tour
of everything possible.

A store's channel choice $(c, w, h)$ fixes exactly which fields the filter is allowed to
see on any given day. One subtlety: the *granularity* of waste counts isn't a fourth
free choice. When waste scanning is on, the counts come back per lot if the register
already reads lot-resolved codes, and only as a storewide total if it doesn't. So waste
resolution is tied to the code-type switch — the model has no combination where you get
per-lot waste detail without also being able to identify lots at the register.

When the delivery-history switch is set to pack date or temperature history, the model
records journey details for each of the three arriving lots — each lot's own upstream
trip, plus one shared leg from the distribution center to the store. The filter then
receives, for that day, whatever the mask allows: a pack date, a temperature trace, or
both, together with which lot each one belongs to. It never receives a freshness value
directly — freshness can't be observed, only inferred. When temperature history is
switched on, the browser-based studio interface also breaks these traces out lot by
lot, so you can see each lot's exposure separately.

## Why it's modelled this way

The three switches are kept independent because register resolution, waste resolution,
and delivery metadata are three separate, teachable ideas. Bundling them into a handful
of fixed presets would hide that independence from the reader. Limiting the interface
to just the ladder's five named scenarios was rejected for the same reason: it wouldn't
show which specific piece of instrumentation — the code type, the waste scan, or the
delivery history — is responsible for an improvement in belief accuracy.

Waste granularity is derived from the code-type switch rather than tracked as its own
free choice. That keeps the model simpler, at the cost of one gap described in the
caveat below.

The code-type switch and the delivery-history switch interact in how the model builds
and tracks lots, but the model doesn't need a fourth switch to handle that interaction.
An LGTIN store holds three separate shelf segments, and each segment's starting
condition depends on that lot's own journey — its transit time or its accumulated
temperature exposure, whichever the delivery-history switch reveals. A UPC store still
receives all three lots' worth of information on the shipment paperwork — three pack
dates, three logger traces — but can't attribute them to specific units on the shelf.
So the filter creates one merged cohort of $Q$ units instead, built from the mixture
$\text{Law}_{\text{UPC}} = (1/L)\sum_\ell \text{Law}(\text{record}_\ell)$ — averaging
the three lots' probability distributions together, not their pack dates. Averaging the
dates directly would erase the spread between lots and understate how uncertain a UPC
store really is.

Because that same fork already determines whether journey data lands in separate lots
or gets mixed into one shared distribution, a fourth switch would only duplicate it.

**Caveat:** because waste granularity is tied to code type, the model can't represent a
store that reads plain UPCs at checkout but still gets per-lot waste detail from a
separate lot-labeled workflow. See [Observation scenarios](./observation-scenarios.md)
for exactly where this shows up.

## In the code

| Concept | Symbol / field | File:line |
| --- | --- | --- |
| Channel triple (the three switches) | `ObsChannels { code_type, scan_waste, delivery_history }` | `crates/voi_core/src/obs.rs:32` |
| Register code-type switch | `CodeType::{Upc, Lgtin}` | `crates/voi_core/src/obs.rs:46` |
| Delivery-history switch | `DeliveryHistory::{None, PackDate, TemperatureHistory}` | `crates/voi_core/src/obs.rs:56` |
| Masked observation (pack date, temperature trace, and lot ID, gated by mask) | `FilterObs` (`pack_date_days`, `temp_times_d`, `temp_temps_c`, `arrival_lot_ids`) | `crates/voi_core/src/obs.rs:90` |
| Channels → observation mask | `mask_from_channels(ch: ObsChannels) -> ObsMask` | `crates/voi_core/src/obs.rs:276` |
| All 12 combinations exercised (regression test) | `mask_from_channels_all_twelve_combos` | `crates/voi_core/src/obs.rs:480` |
| Waste granularity coupled to code type | `if ch.code_type == CodeType::Lgtin { m.waste_by_lot = true }` | `crates/voi_core/src/obs.rs:290` |
| TypeScript port (studio UI), incl. per-lot temperature traces on the wire | `ObsChannels`, `maskFromChannels`, `temp_traces_by_lot` | `web/src/obsMask.ts:20`, `web/src/obsMask.ts:132`, `web/src/obsMask.ts:46` |
| Python port (research path) | `ObsChannels` dataclass | `src/blueberries_voi/filter/types.py:162` |

## Caveats

The channel grid says nothing about *how good* an instrument is once installed — a
temperature logger that samples once a day and one that samples every hour both set
delivery history to temperature history; the model doesn't currently distinguish
sampling density within a channel. It also says nothing about cost: buying a channel is
a business decision covered narratively on the
[Observation scenarios](./observation-scenarios.md) page, not something the grid itself
prices. And as noted above, the grid can't represent "lot-resolved waste without
lot-resolved POS."
