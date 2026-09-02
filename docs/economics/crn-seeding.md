---
title: Same weather, different glasses
sources:
  code: [crates/voi_core/src/voi.rs, crates/voi_core/src/spawn_rng.rs, src/blueberries_voi/rng.py, crates/voi_core/src/arrival.rs]
---

# Same weather, different glasses

The Value of Information (VOI) experiment compares what a store earns under several different observation scenarios, arranged along a ladder from minimal information (books only) up to richer scanning and delivery history. For that comparison to mean anything, the profit differences it finds need to come from what each scenario can see. They shouldn't come from one scenario happening to draw a luckier week of demand and spoilage than another. The project's random-number scheme exists to rule that second explanation out.

## The idea

Picture several observers watching the same week unfold in the same store: the same customers walk in on the same days, the same trucks arrive carrying berries at the same true freshness, and the same units spoil on the same flips of the coin. What differs between the observers is only which pair of glasses each one is wearing — how much of that shared reality they're allowed to see.

The site's main mental model for these glasses is a 5-rung ladder, from least to most information:

1. **Books only** — how many units were delivered and how many were sold. This is roughly what nearly every store already tracks.
2. **+ scan waste** — also scans what got thrown out, via waste scanning.
3. **+ pack date** — also knows the pack date on each delivery.
4. **+ LGTIN** — can trace which unit came from which delivery batch, using an LGTIN (a barcode that identifies not just the product but the specific lot it came from).
5. **+ temp. history** — also has a logged temperature history for the delivery.

Beyond this main ladder, a couple of extra presets show up elsewhere in the project as additional detail, not part of the core comparison: one observer can trace which lot a sold unit came from with no delivery history at all ("lot ID at point of sale (POS)"), and one — the oracle — is simply told the true state of every unit on the shelf (a hypothetical observer who's told the true state of every unit, used as an upper bound on how much information could possibly help).

If each scenario ran its own independently randomized week, any profit difference we measured would be mixed together with ordinary Monte Carlo noise — one week might just have fewer stockouts or less spoilage by chance, on top of whatever the glasses actually bought a policy. Sharing the identical week's demand, spoilage, and true arrival freshness across every scenario cancels that luck out. This technique is called common random numbers (CRN) — holding the random draws fixed across scenarios so only what's observed differs. What's left over is much closer to the true effect of what each scenario's filter could see.

## The math

The mechanism is a deterministic function from a small set of coordinates to a reproducible stream of random numbers. Asking for the same coordinates twice — from Rust or from Python — always regenerates the identical draws, and different coordinates never collide. A draw is addressed by four pieces:

- $\text{root\_seed}$ — the top-level seed for one replication of the whole experiment,
- a run/tag label identifying *who* is drawing (the shared physics, or one particular scenario's filter),
- $\text{day}$ — the calendar day within the episode,
- a stream name identifying *what kind* of randomness is being drawn (demand, spoilage, filter resampling, and so on).

The reference implementation builds this address by hashing the four coordinates into an entropy pool and feeding it through NumPy's random-number-seeding algorithm (`SeedSequence`) — reimplemented bit-for-bit in Rust so the two languages produce identical draws from the same coordinates, verified by a shared test (see the table below). Two different streams under the same root seed, run, and day never interfere with each other: consuming many draws from one stream does not shift what the next draw from a different stream produces.

## Why it's modelled this way

CRN is applied across the entire observation ladder using one shared set of random draws, not just within a narrower slice of the comparison. Every observation scenario differs only in what a policy is allowed to observe, never in the underlying physical process — the same demand, the same spoilage, and the same truck arrivals happen regardless of which scenario is watching. That's exactly why it's valid, and important, to reuse the identical realization across the whole ladder rather than re-randomizing per scenario. Skipping this and letting each scenario draw its own random week would reintroduce the same signal-to-noise problem CRN exists to solve. Pairing scenarios only in smaller groups, rather than across the whole ladder at once, would reduce the noise less, since different groups could still drift apart on different physical draws.

Concretely, every random draw is looked up by an explicit address — the four coordinates above — rather than pulled in order from one long, shared sequence of numbers. That addressing scheme is organized as a tree of derived random-number generators, each one keyed to a specific combination of run, day, and stream. Doing it this way protects against a subtle failure mode: a scheme that instead drew numbers sequentially from one shared stream could desync silently. The moment two scenarios draw a different number of random values, their streams drift apart with no error and no visible symptom — just quietly worse decisions from then on. Pre-generating and storing every draw ahead of time, indexed by address, was considered too, but the memory and storage cost across a full sweep of experiments ruled it out as the default; that approach stays available if a specific stream's reproducibility ever needs to be checked by hand.

**Caveat — two implementations.** The scheme above exists twice, once in each language the project uses day to day, and the two aren't required to produce identical numbers except where a test explicitly checks that. The NumPy-compatible version (see the code table below) seeds the interactive Studio session, the controller's rollout, and alpha-tuning, and is verified to produce bit-identical draws to NumPy across languages by a shared cross-language test. The dedicated calculation that produces the project's headline profit-by-scenario numbers implements the same architectural idea — the same four coordinates, a shared-truth tag plus a per-scenario filter tag — but through its own, separate hashing method rather than by routing through the NumPy-compatible primitive. The pairing guarantee (same physics, different glasses) holds either way, but the two code paths do not produce identical numbers from the same coordinates. The headline VOI numbers shouldn't be assumed to equal what the NumPy-compatible primitive would produce for the same inputs.

## In the code

| Concept | Symbol | File:line |
| --- | --- | --- |
| Physics tag shared by every observation scenario, every day | `physics_tag()` | `crates/voi_core/src/voi.rs:71` |
| Per-scenario filter tag (only the filter's own randomness differs by scenario) | `filter_tag(scenario)` | `crates/voi_core/src/voi.rs:78` |
| Demand draws (shared truth) | `STREAM_DEMAND` | `crates/voi_core/src/voi.rs:28` |
| Sales-allocation draws (shared truth) | `STREAM_ALLOC` | `crates/voi_core/src/voi.rs:29` |
| Gamma-aging draws (shared truth) | `STREAM_GAMMA` | `crates/voi_core/src/voi.rs:30` |
| Filter's own internal randomness (per-scenario, not shared) | `STREAM_FILTER` | `crates/voi_core/src/voi.rs:35` |
| Birth-freshness spread draws | `STREAM_BIRTH` | `crates/voi_core/src/voi.rs:37` |
| Arrival within-pallet position draw | `STREAM_ARRIVAL_POS` | `crates/voi_core/src/voi.rs:39` |
| Arrival gamma-loss draw | `STREAM_ARRIVAL_GAMMA` | `crates/voi_core/src/voi.rs:41` |
| Arrival transit-duration draw | `STREAM_ARRIVAL_DURATION` | `crates/voi_core/src/voi.rs:44` |
| Arrival transit-temperature draw | `STREAM_ARRIVAL_TEMP` | `crates/voi_core/src/voi.rs:47` |
| Named arrival streams shared with rollout / interactive session | `STREAM_ARRIVAL_DURATION` / `_TEMP` / `_POS` / `_GAMMA` | `crates/voi_core/src/arrival.rs:61-69` |
| NumPy-`SeedSequence`-compatible RNG (rollout, alpha-tune, interactive session — not the VOI cell above) | `SpawnRng::spawn_rng` | `crates/voi_core/src/spawn_rng.rs:34` |
| Same primitive, Python side | `spawn_rng` | `src/blueberries_voi/rng.py:36` |
| Cross-language bit-identical fixture (Rust side) | `ac8_birth_stream_next_u64_fixture` | `crates/voi_core/src/spawn_rng.rs:189` |
| Cross-language bit-identical fixture (Python side) | `test_birth_spawn_rng_matches_rust_next_u64_fixture` | `tests/test_rng.py:65` |

## Caveats

- Full CRN removes ordinary Monte Carlo noise across the ladder; it does not by itself make one seed's profit number a good estimate of the population mean. Reporting a defensible number still needs many replications and a paired bootstrap confidence interval — see [the VOI metric](/economics/voi-metric).
- The filter's own resampling randomness is deliberately tagged per scenario rather than shared (see the table above). Each scenario runs a differently-shaped filter, since different scenarios mask different observations. Only the underlying physical truth is meant to be shared across scenarios — never the filter's own internals.
- The dedicated calculation behind the headline VOI numbers uses its own hashing method, not literally the NumPy `SeedSequence` algorithm described above. Only the separate NumPy-compatible primitive carries the verified bit-identical-to-NumPy guarantee.
- Adding a new observation scenario means carefully deciding which random draws count as shared truth and which belong only to that scenario's filter. Getting this split wrong — sharing something that should differ, or the reverse — would silently reintroduce the exact Monte Carlo noise this scheme exists to remove, with no error to flag the mistake.
