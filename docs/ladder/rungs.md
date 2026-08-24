---
title: The seven named rungs
sources:
  code: [crates/voi_core/src/obs.rs, web/src/obsMask.ts]
---

# The seven named rungs

The [observation grid](./channels.md) has 12 reachable combinations, but most of the
project's charts, tests, and VOI sweeps refer to just seven named points on it: P0, P1,
F1, F1s, F2a, F2, F3. These are **presets**, not separate models — each one is a fixed
choice of the same three channel switches, kept as a named shorthand because they trace
a plausible investment path a real grocer would walk, cheapest first.

> **Figure (coming soon):** a vertical ladder diagram of the seven rungs, each row
> showing its channel triple and a one-line "what you'd have to buy" caption.

## The idea

Reading down the table below, each rung adds one piece of real-world instrumentation.
P0 assumes nothing beyond what every grocery store already has (a point-of-sale system
and a receiving log). Every rung after that corresponds to a purchase or a process
change: a handheld scanner, a barcode format that carries lot identity, a line on a
supplier's paperwork, a logger that rides in the truck. None of these devices measures
freshness — they only change what shows up in the daily observation log, and the filter
has to do all the work of turning that log into a belief about freshness.

## The math

Each rung is a fixed point $(c, w, h)$ in the grid from [Channels](./channels.md). The
code exposes this as a lookup, `channels_for_preset(id)`, and its inverse,
`preset_for_channels(ch)`, which returns a name only when the channel triple exactly
matches one of the seven presets — any other combination reports as "custom" rather than
forcing a nearest-rung label.

## Why it's modelled this way

The named presets exist so that value-of-information sweeps and charts can be keyed by a
short rung id rather than a raw channel triple. The seven names are also chosen to track
a real adoption story — cheap process changes first, capital purchases later — which is
why this page frames each row as a purchasing decision rather than just a row in a truth
table.

**Caveat — F1 and F1s currently collapse to the same rung.** F1 ("lot ID at POS") and
F1s ("lot ID on the shrink gun") describe two different instruments: F1 reads lot codes
at checkout with storewide waste counts, while F1s reads plain UPCs at checkout but
reads lot codes on the *waste* gun, giving per-lot waste with no change to the register.
Because waste granularity is derived from the POS code-type switch (see
[Channels](./channels.md)), the current model cannot produce that second combination — a
store cannot get per-lot waste without also reading lot codes at POS. `channels_for_preset`
reflects this directly: its match arm handles `"F1" | "F1s"` together and returns the
identical `ObsChannels` value for both, and a dedicated test
(`mask_for_f1s_matches_f1`) asserts the two masks are equal. F1s survives in the UI and
in VOI sweeps as a distinct label, but it currently teaches nothing that F1 does not.

## In the code

| Rung | Channels (code_type, scan_waste, delivery_history) | Business translation | File:line |
| --- | --- | --- | --- |
| **P0** — books only | upc, off, none | Nothing beyond ordinary POS and receiving — no new purchase. | `crates/voi_core/src/obs.rs:137` |
| **P1** — shrink gun | upc, on, none | Buy a handheld scanner for daily storewide waste counts; no barcode change. | `crates/voi_core/src/obs.rs:142` |
| **F1** — lot ID at POS | gsin, on, none | Switch checkout to lot-resolved (GSIN) codes; waste counts come back per lot as a side effect. | `crates/voi_core/src/obs.rs:147` |
| **F1s** — lot ID on the shrink gun | gsin, on, none *(identical to F1 — see caveat above)* | Intended design: keep UPC at checkout, put lot-resolved codes only on the waste gun. Not separately representable in the current code. | `crates/voi_core/src/obs.rs:147` |
| **F2a** — pack date on the supplier ASN | upc, on, pack_date | Get the supplier to print/transmit a pack date on the ASN; no barcode change at the register. | `crates/voi_core/src/obs.rs:152` |
| **F2** — lot ID + pack date | gsin, on, pack_date | Both of the above: lot-resolved POS codes and a supplier pack date. | `crates/voi_core/src/obs.rs:157` |
| **F3** — + temperature history | gsin, on, temperature_history | All of F2, plus a temperature logger that travels with the pallet and is read at receipt. | `crates/voi_core/src/obs.rs:162` |
| Preset table (TS mirror) | `PRESET_CHANNELS` | Studio UI reads the same seven presets. | `web/src/obsMask.ts:68` |
| Round-trip test (all 7 presets) | `preset_round_trip_matches_mask_for` | | `crates/voi_core/src/obs.rs:414` |
| F1s ≡ F1 assertion | `mask_for_f1s_matches_f1` | | `crates/voi_core/src/obs.rs:484` |

## Caveats

The "business translation" column is illustrative narrative, not something the code
enforces or prices — the model has no cost field for a shrink gun or a temperature
logger. The rung names also do not imply a strict information ordering on every metric;
[No channel observes freshness](./no-channel-observes-freshness.md) explains why later
rungs sharpen belief in a specific, checkable sense (a narrower distribution over
freshness) rather than "more data always better" in some vague sense. And as covered
above, F1s is presently a relabeling of F1, not an independent instrument — readers
comparing F1 vs. F1s results anywhere in this project should expect no difference, and
that is expected behavior of the current code, not a bug in the comparison.
