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

Every belief the filter holds is built from three independent choices about what the
store *instruments*: what code gets scanned at the register, whether waste gets scanned
at all, and what the supplier tells you about a shipment's journey. Nothing else feeds
the model — there is no fourth channel and no way to observe freshness directly.
Understanding this grid helps in reading the rest of this section, since the seven named
[observation scenarios](./observation-scenarios.md) are just labels for points on it.

## The idea

Think of a grocer choosing hardware and process. There are three independent switches:

1. **What code does the register read?** A plain UPC barcode (identical for every unit
   of a product, so the register cannot tell one delivery from another), or a
   lot-resolved code — a LGTIN-style code that also encodes *which delivery segment* a
   unit came from.
2. **Does anyone scan waste?** Off (spoiled units are simply removed and never counted),
   or on (a handheld scanner scans culled units, producing daily counts).
3. **What does the supplier tell you about the shipment's journey?** Nothing beyond
   quantity, pack dates stamped on the delivery paperwork (the ASN), or full
   temperature-history traces from loggers that rode with the pallet.

Each switch is independent of the other two — a store could run lot-resolved codes at
POS with a temperature-logged pallet but *no* waste scanning at all, and the model
handles that combination the same way it handles any named observation scenario. That
independence is the point of the design: it shows what each *kind* of instrument buys
you, rather than bundling everything into a handful of fixed packages.

Under ADR 0149 every delivery carries **three fixed lots** (`L = 3`): total case quantity
is **split** across those lots, not multiplied. That changes what LGTIN buys. With a
single shelf cohort, lot identity on a M/W/F schedule was nearly redundant with how long
each cohort had been on the shelf — age alone nearly pinned sales allocation, so LGTIN
added almost nothing beyond a pack date. With three coexisting segments from the same
truck, lot identity now separates **composition** (how many units sit in each segment),
**sequential attribution** (which segment sales drained), and **lot count** (whether the
shelf still holds three distinguishable cohorts). LGTIN is meaningful again because those
channels are not recoverable from pooled totals alone.

## The math

The three switches form a small discrete space. Writing the code-type switch as
$c \in \{\text{upc}, \text{lgtin}\}$, the waste-scan switch as $w \in \{\text{off},
\text{on}\}$, and the delivery-history switch as $h \in \{\text{none}, \text{pack\_date},
\text{temperature\_history}\}$, the full space of instrumented stores is the product

$$
|c| \times |w| \times |h| = 2 \times 2 \times 3 = 12 \text{ combinations.}
$$

A store's channel choice $(c, w, h)$ deterministically fixes which fields the filter is
allowed to see on any given day — this mapping is called the **observation mask**. One
subtlety: the *granularity* of waste counts is not a fourth free choice. When waste
scanning is on, the counts come back **per lot** if the POS already reads lot-resolved
codes ($c = \text{lgtin}$), and only as a **storewide total** if it does not ($c =
\text{upc}$). So waste resolution is coupled to the code-type switch — the model does
not offer a combination where you get per-lot waste detail without also being able to
identify lots at the register.

When $h$ is `pack_date` or `temperature_history`, the truth path records journey
metadata for each of the three arriving lots (each lot's own upstream draw plus one
shared DC→store leg). `FilterObs` exposes whatever the mask allows — `pack_date_days`,
`temp_times_d` / `temp_temps_c`, and `arrival_lot_ids` aligned to those lots — not a
freshness value. On the studio wire, per-lot traces also appear as
`temp_traces_by_lot` when temperature history is enabled.

## Why it's modelled this way

The three switches are kept orthogonal because POS resolution, waste resolution, and
delivery metadata are independent teaching axes. Collapsing them into a handful of fixed
presets would hide that independence from the reader. Keeping the named observation
scenarios as the only selectable unit was rejected as the sole interface because it would
not show which *component* of instrumentation is driving an information gain.

Waste granularity is derived from the POS code-type switch rather than tracked as its
own free choice, which keeps the model simpler at the cost of one representational gap,
described below.

**Structural fork (ADR 0149).** `code_type` and `delivery_history` interact in truth
and birth, but not via a fourth mask field. A LGTIN store holds three shelf segments; each
segment's birth law is conditioned on that lot's own journey (`Duration(d_ℓ)` or
`Exposure(Λ_ℓ)` under ADR 0150). A UPC store still receives all three lots on the ASN —
three pack dates, three logger traces — but cannot attribute them, so the filter births
one merged cohort of $Q$ units from the mixture law
$\text{Law}_{\text{UPC}} = (1/L)\sum_\ell \text{Law}(\text{record}_\ell)$. **Mix the
laws, don't average the dates:** averaging pack dates first would discard between-lot
spread and understate UPC uncertainty.

An earlier draft proposed a coupled `delivery_history_by_lot` mask field so a LGTIN store
could see per-lot journey data while a UPC store saw only pooled journey data. That
field is **rejected** — the `code_type` / `delivery_history` fork already determines
whether journey data lands in segments or is mixed into one law, so a third field would
duplicate information the fork already encodes.

**Caveat:** because waste granularity is coupled to code type, the model cannot
represent a store that reads plain UPCs at checkout but gets per-lot waste detail from a
separate lot-labeled workflow. See [Observation scenarios](./observation-scenarios.md)
for exactly where this shows up.

## In the code

| Concept | Symbol / field | File:line |
| --- | --- | --- |
| Channel triple (the three switches) | `ObsChannels { code_type, scan_waste, delivery_history }` | `crates/voi_core/src/obs.rs:32` |
| POS code-type switch | `CodeType::{Upc, Lgtin}` | `crates/voi_core/src/obs.rs:46` |
| Delivery-history switch | `DeliveryHistory::{None, PackDate, TemperatureHistory}` | `crates/voi_core/src/obs.rs:56` |
| Masked observation (journey fields gated by mask) | `FilterObs` (`pack_date_days`, `temp_times_d`, `temp_temps_c`, `arrival_lot_ids`) | `crates/voi_core/src/obs.rs:90` |
| Channels → observation mask | `mask_from_channels(ch: ObsChannels) -> ObsMask` | `crates/voi_core/src/obs.rs:276` |
| All 12 combinations exercised | `mask_from_channels_all_twelve_combos` (test) | `crates/voi_core/src/obs.rs:480` |
| Waste granularity coupled to code type | `if ch.code_type == CodeType::Lgtin { m.waste_by_lot = true }` | `crates/voi_core/src/obs.rs:290` |
| TypeScript port (studio UI) | `ObsChannels`, `maskFromChannels`, `temp_traces_by_lot` on wire | `web/src/obsMask.ts:20`, `web/src/obsMask.ts:132`, `web/src/obsMask.ts:46` |
| Python port (research path) | `ObsChannels` dataclass | `src/blueberries_voi/filter/types.py:162` |

## Caveats

The channel grid says nothing about *how good* an instrument is once installed — a
temperature logger that samples once a day and one that samples every hour both set
`delivery_history = temperature_history`; the model does not currently distinguish
sampling density within a channel. It also says nothing about cost: buying a channel is
a business decision covered narratively on the
[Observation scenarios](./observation-scenarios.md) page, not something the grid itself
prices. And as noted above, the grid cannot represent "lot-resolved waste without
lot-resolved POS."
