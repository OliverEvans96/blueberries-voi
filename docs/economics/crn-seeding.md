---
title: Same weather, different glasses
sources:
  code: [crates/voi_core/src/voi.rs, crates/voi_core/src/spawn_rng.rs, src/blueberries_voi/rng.py, crates/voi_core/src/arrival.rs]
---

# Same weather, different glasses

The VOI experiment compares what a store earns under several different observation scenarios — from books-only up through richer scanning and a perfect-state oracle. For that comparison to mean anything, the profit numbers it produces need to differ *because* the scenarios see different things, not because one scenario happened to draw a luckier week of demand and spoilage than another. The project's random-number scheme exists to rule that second explanation out.

![Scored profit per observation scenario under one shared root_seed=42 physics realization, with a books-only baseline dashed line](/figures/crn-profit-by-scenario.png)

## The idea

Imagine seven observers watching the same week unfold in the same store — the same customers walk in on the same days, the same trucks arrive carrying berries at the same true freshness, the same units spoil on the same flips of the coin. What differs between the seven is only which pair of glasses each one is wearing: one can only read the cash-register tape ("books only"), another additionally gets a scan of what got thrown out ("shrink gun"), another can trace which lot a sold unit came from ("lot ID at POS"), and so on up to an observer that gets told the true state of every unit on the shelf (the oracle).

If instead each scenario ran its own independently-randomized week, any profit difference measured would be mixed together with ordinary Monte Carlo noise — one week just having fewer stockouts or less spoilage by chance — on top of whatever the glasses actually bought a policy. Sharing the identical week's demand, spoilage, and true arrival freshness across every scenario (a technique called common random numbers, or CRN) cancels that luck out. What's left over is much closer to the effect of what each scenario's filter could see.

## The math

The mechanism is a deterministic function from a small set of coordinates to a reproducible stream of random numbers: asking for the same coordinates twice — from Rust or from Python — always regenerates the identical draws, and different coordinates never collide. A draw is addressed by four pieces:

- $\text{root\_seed}$ — the top-level seed for one replication of the whole experiment,
- a run/tag label identifying *who* is drawing (the shared physics, or one particular scenario's filter),
- $\text{day}$ — the calendar day within the episode,
- a stream name identifying *what kind* of randomness is being drawn (demand, spoilage, filter resampling, ...).

The reference implementation (`SpawnRng` in Rust, `spawn_rng` in Python) builds this address by hashing the four coordinates into an entropy pool and feeding it through NumPy's `SeedSequence` state-generation algorithm — reimplemented bit-for-bit in Rust so the two languages produce identical draws from the same coordinates, verified by a shared fixture (see the table below). Two different streams under the same $(\text{root\_seed}, \text{run}, \text{day})$ never interfere with each other: consuming many draws from one stream does not shift what the next draw from a different stream produces.

## Why it's modelled this way

CRN is applied across the entire knowledge ladder at a fixed $\beta$, not just within a rollout's inner candidate loop. Every observation scenario differs only in **what a policy is allowed to observe**, never in the underlying physical process, so the identical realization is valid to reuse across the whole ladder. Running the outer loop with no CRN at all would be noisy and reintroduce the same signal-to-noise problem CRN exists to solve. Pairing policies only within one scenario/$\beta$ arm would reduce noise less, since different scenario arms could still drift apart on different physical draws.

The addressing scheme underneath this is a hierarchical SeedSequence spawn tree, keyed by semantic slot — $(\text{run}, \text{day}, \text{stream})$ — rather than a single global RNG consumed sequentially. A sequential scheme is dangerous because it can desync *silently*: the moment two arms draw a different number of random variates, their streams drift apart with no error and no visible symptom, just quietly worse decisions. Pre-generating and storing every draw as arrays indexed by slot was considered too, but the memory and storage cost across a full sweep ruled it out as the default; it stays available if a specific stream's reproducibility ever needs auditing by hand.

**Caveat — two implementations.** The NumPy-`SeedSequence`-compatible scheme described above (`SpawnRng` / `spawn_rng`) seeds the interactive Studio session, the controller's rollout, and alpha-tuning, and is verified bit-identical to NumPy across languages by a shared cross-language fixture. The dedicated VOI CRN cell that produces the project's headline profit-by-scenario numbers, `run_voi_crn_cell` in `voi.rs`, implements the same architectural idea — the same four coordinates, a shared physics tag vs. a per-scenario filter tag — but through its own lighter-weight wrapping-multiply hash rather than by routing through `SpawnRng`; its own source comment flags this explicitly as "not NumPy-bit CRN." The pairing guarantee (same physics, different glasses) holds either way, but the two code paths do not produce byte-identical numbers from the same coordinates, and a reader should not assume the VOI cell's Rust streams equal what a NumPy `SeedSequence` call would produce for the same inputs.

## In the code

| Concept | Symbol | File:line |
| --- | --- | --- |
| Physics tag shared by every observation scenario, every day | `physics_tag()` | `crates/voi_core/src/voi.rs:57` |
| Per-scenario filter tag (only the filter's own randomness differs by scenario) | `filter_tag(scenario)` | `crates/voi_core/src/voi.rs:61` |
| Demand draws (shared truth) | `STREAM_DEMAND` | `crates/voi_core/src/voi.rs:24` |
| Sales-allocation draws (shared truth) | `STREAM_ALLOC` | `crates/voi_core/src/voi.rs:25` |
| Gamma-aging draws (shared truth) | `STREAM_GAMMA` | `crates/voi_core/src/voi.rs:26` |
| Filter's own internal randomness (per-scenario, not shared) | `STREAM_FILTER` | `crates/voi_core/src/voi.rs:31` |
| Birth-freshness spread draws | `STREAM_BIRTH` | `crates/voi_core/src/voi.rs:33` |
| Arrival within-pallet position draw | `STREAM_ARRIVAL_POS` | `crates/voi_core/src/voi.rs:35` |
| Arrival gamma-loss draw | `STREAM_ARRIVAL_GAMMA` | `crates/voi_core/src/voi.rs:37` |
| Arrival transit-duration draw | `STREAM_ARRIVAL_DURATION` | `crates/voi_core/src/voi.rs:40` |
| Arrival transit-temperature draw | `STREAM_ARRIVAL_TEMP` | `crates/voi_core/src/voi.rs:43` |
| Named arrival streams shared with rollout / interactive session | `STREAM_ARRIVAL_DURATION` / `_TEMP` / `_POS` / `_GAMMA` | `crates/voi_core/src/arrival.rs:18-21` |
| NumPy-`SeedSequence`-compatible RNG (rollout, alpha-tune, interactive session — not the VOI cell above) | `SpawnRng::spawn_rng` | `crates/voi_core/src/spawn_rng.rs:23` |
| Same primitive, Python side | `spawn_rng` | `src/blueberries_voi/rng.py:36` |
| Cross-language bit-identical fixture (Rust side) | `ac8_birth_stream_next_u64_fixture` | `crates/voi_core/src/spawn_rng.rs:166` |
| Cross-language bit-identical fixture (Python side) | `test_birth_spawn_rng_matches_rust_next_u64_fixture` | `tests/test_rng.py:65` |

## Caveats

- Full CRN removes ordinary Monte Carlo noise across the knowledge ladder; it does not by itself make one seed's profit number a good estimate of the population mean. Reporting a defensible number still needs many replications and a paired bootstrap confidence interval — see [the VOI metric](/economics/voi-metric).
- The filter's own resampling randomness (`STREAM_FILTER`) is deliberately tagged per-scenario, not shared — each scenario runs a differently-shaped filter (different scenarios mask different observations), so only the underlying physical truth is meant to be shared, never the filter's internals.
- The production VOI CRN cell's seed-mixing function is a bespoke hash, not literally NumPy's `SeedSequence` algorithm (see the caveat above) — only the separate `SpawnRng` / `rng.py` primitive carries the verified bit-identical-to-NumPy guarantee.
- Getting the physics-tag-vs-filter-tag split wrong when adding a new observation scenario — sharing a tag that should differ, or vice versa — would silently reintroduce the exact Monte Carlo noise this scheme exists to remove, with no error to flag the mistake.
