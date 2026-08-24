---
title: Observation channels
sources:
  adr: [0133, 0144]
  code:
    [crates/voi_core/src/obs.rs, web/src/obsMask.ts, src/blueberries_voi/filter/types.py]
---

# What a store can actually see

Every belief the filter holds is built from three independent choices about what the
store *instruments*: what code gets scanned at the register, whether waste gets scanned
at all, and what the supplier tells you about a shipment's journey. Nothing else feeds
the model — there is no fourth secret channel and no way to observe freshness directly.
Understanding this grid is the key to reading every other page in this section, because
the named "rungs" (P0, P1, F1, ...) are just convenient labels for points on it.

> **Figure (coming soon):** a 2×2×3 grid diagram showing the three channel axes (POS
> code type, waste scanning, delivery history) with the 12 resulting combinations, and
> the seven named presets highlighted as a subset of that grid.

## The idea

Think of a grocer choosing hardware and process, not physics. There are three
independent switches:

1. **What code does the register read?** A plain UPC barcode (identical for every unit
   of a product, so the register cannot tell one delivery from another), or a
   lot-resolved code — a GSIN-style code that also encodes *which delivery* a unit came
   from.
2. **Does anyone scan waste?** Off (spoiled units are simply removed and never counted),
   or on (a handheld "shrink gun" scans culled units, producing daily counts).
3. **What does the supplier tell you about the shipment's journey?** Nothing beyond
   quantity, a pack date stamped on the delivery paperwork (the ASN), or a full
   temperature-history trace from a logger that rode with the pallet.

Each switch is independent of the other two — a store could run lot-resolved codes at
POS with a temperature-logged pallet but *no* waste scanning at all, and the model
handles that combination exactly the same way it handles any named rung. That
independence is the whole point of the design: it lets the model teach "what does each
*kind* of instrument buy you" rather than bundling everything into a handful of fixed
packages.

## The math

The three switches form a small discrete space. Writing the code-type switch as
$c \in \{\text{upc}, \text{gsin}\}$, the waste-scan switch as $w \in \{\text{off},
\text{on}\}$, and the delivery-history switch as $h \in \{\text{none}, \text{pack\_date},
\text{temperature\_history}\}$, the full space of instrumented stores is the product

$$
|c| \times |w| \times |h| = 2 \times 2 \times 3 = 12 \text{ combinations.}
$$

A store's channel choice $(c, w, h)$ deterministically fixes which fields the filter is
allowed to see on any given day — this mapping is called the **observation mask**. One
subtlety worth flagging explicitly: the *granularity* of waste counts is not a fourth
free choice. When waste scanning is on, the counts come back **per lot** if the POS
already reads lot-resolved codes ($c = \text{gsin}$), and only as a **storewide total**
if it does not ($c = \text{upc}$). So "waste resolution" is coupled to the code-type
switch, not independent of it — the model does not offer a combination where you get
per-lot waste detail without also being able to identify lots at the register.

## Why it's modelled this way

ADR 0133 chose orthogonal channel toggles specifically to replace an earlier six-chip
"pick a named ladder rung" UI. The stated reason: POS resolution, waste resolution, and
delivery metadata are independent teaching axes, and collapsing them into fixed presets
hid that independence from the reader. The alternative — keep the ladder as the only
selectable unit — was rejected because it does not teach which *component* of
instrumentation is driving an information gain.

ADR 0133 originally specified waste resolution as its own three-way switch (`none`,
`daily_counts`, `lot_id`) independent of POS resolution. A later implementation pass
(T-135, "global scan `ObsChannels` model") collapsed that into the single `scan_waste`
boolean described above, deriving per-lot-vs-storewide granularity from the POS
code-type switch instead of tracking it separately. That collapse is a fact about the
current code, not something recorded in its own ADR — the module doc comment simply
notes it "supersedes ADR 0133 pos/waste/deliveries."

**Caveat:** because waste granularity is coupled to code type, the model cannot
represent a store that reads plain UPCs at checkout but gets per-lot waste detail from a
separate lot-labeled shrink-gun workflow. ADR 0133 explicitly intended that combination
to be valid (its alternatives section calls out "F1s is valid" as a reason *not* to
couple the two). The current implementation does not produce that combination — see
[Rungs](./rungs.md) for exactly where this shows up.

## In the code

| Concept | Symbol / field | File:line |
| --- | --- | --- |
| Channel triple (the three switches) | `ObsChannels { code_type, scan_waste, delivery_history }` | `crates/voi_core/src/obs.rs:23` |
| POS code-type switch | `CodeType::{Upc, Gsin}` | `crates/voi_core/src/obs.rs:31` |
| Delivery-history switch | `DeliveryHistory::{None, PackDate, TemperatureHistory}` | `crates/voi_core/src/obs.rs:38` |
| Channels → observation mask | `mask_from_channels(ch: ObsChannels) -> ObsMask` | `crates/voi_core/src/obs.rs:209` |
| All 12 combinations exercised | `mask_from_channels_all_twelve_combos` (test) | `crates/voi_core/src/obs.rs:382` |
| Waste granularity coupled to code type | `if ch.code_type == CodeType::Gsin { m.waste_by_lot = true }` | `crates/voi_core/src/obs.rs:224` |
| TypeScript port (studio UI) | `ObsChannels`, `maskFromChannels` | `web/src/obsMask.ts:20`, `web/src/obsMask.ts:131` |
| Python port (research path) | `ObsChannels` dataclass | `src/blueberries_voi/filter/types.py:160` |

## Caveats

The channel grid says nothing about *how good* an instrument is once installed — a
temperature logger that samples once a day and one that samples every hour both set
`delivery_history = temperature_history`; the model does not currently distinguish
sampling density within a channel. It also says nothing about cost: buying a channel is
a business decision covered narratively on the [Rungs](./rungs.md) page, not something
the grid itself prices. And as noted above, the grid cannot represent "lot-resolved
waste without lot-resolved POS" even though an earlier design intended it to.
