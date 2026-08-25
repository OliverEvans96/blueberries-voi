---
title: The seven named observation scenarios
sources:
  code: [crates/voi_core/src/obs.rs, web/src/obsMask.ts]
---

# The seven named observation scenarios

The [observation grid](./channels.md) has 12 reachable combinations, but most of the
project's charts, tests, and VOI sweeps refer to just seven named points on it. These are
**presets**, not separate models — each one is a fixed choice of the same three channel
switches, kept as a named shorthand because they trace a plausible investment path a real
grocer would walk, cheapest first.

> **Figure (coming soon):** a vertical ladder diagram of the seven observation scenarios,
> each row showing its channel triple and a one-line "what you'd have to buy" caption.

## The idea

Reading down the table below, each scenario adds one piece of real-world instrumentation.
The baseline scenario assumes nothing beyond what every grocery store already has (a
point-of-sale system and a receiving log). Every scenario after that corresponds to a
purchase or a process change: a handheld scanner, a barcode format that carries lot
identity, a line on a supplier's paperwork, a logger that rides in the truck. None of
these devices measures freshness — they only change what shows up in the daily
observation log, and the filter has to do all the work of turning that log into a belief
about freshness.

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
| **Books only** | upc, off, none | Nothing beyond ordinary POS and receiving — no new purchase. | `crates/voi_core/src/obs.rs:137` |
| **Shrink gun** | upc, on, none | Buy a handheld scanner for daily storewide waste counts; no barcode change. | `crates/voi_core/src/obs.rs:142` |
| **Lot ID at POS** | gsin, on, none | Switch checkout to lot-resolved (GSIN) codes; waste counts come back per lot as a side effect. | `crates/voi_core/src/obs.rs:147` |
| **Lot ID on the shrink gun** | gsin, on, none *(identical to "Lot ID at POS" — see caveat above)* | Intended design: keep UPC at checkout, put lot-resolved codes only on the waste gun. Not separately representable in the current code. | `crates/voi_core/src/obs.rs:147` |
| **Pack date on the ASN** | upc, on, pack_date | Get the supplier to print/transmit a pack date on the ASN; no barcode change at the register. | `crates/voi_core/src/obs.rs:152` |
| **Lot ID + pack date** | gsin, on, pack_date | Both of the above: lot-resolved POS codes and a supplier pack date. | `crates/voi_core/src/obs.rs:157` |
| **Lot ID + pack date + temperature history** | gsin, on, temperature_history | All of the previous scenario, plus a temperature logger that travels with the pallet and is read at receipt. | `crates/voi_core/src/obs.rs:162` |
| Preset table (TS mirror) | `PRESET_CHANNELS` | Studio UI reads the same seven presets. | `web/src/obsMask.ts:68` |
| Round-trip test (all 7 presets) | `preset_round_trip_matches_mask_for` | | `crates/voi_core/src/obs.rs:414` |
| "Lot ID on the shrink gun" ≡ "Lot ID at POS" assertion | `mask_for_f1s_matches_f1` | | `crates/voi_core/src/obs.rs:484` |

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
