---
title: Same weather, different glasses
sources:
  adr: [0065, 0068]
  code: [crates/voi_core/src/voi.rs, crates/voi_core/src/spawn_rng.rs, src/blueberries_voi/rng.py, crates/voi_core/src/arrival.rs]
---

# Same weather, different glasses

The VOI experiment compares what a store earns under several different knowledge rungs — from books-only up through richer scanning and a perfect-state oracle. For that comparison to mean anything, the seven profit numbers it produces need to differ *because* the rungs see different things, not because one rung happened to draw a luckier week of demand and spoilage than another. The project's random-number scheme exists specifically to rule that second explanation out.

![Scored profit per knowledge rung under one shared root_seed=42 physics realization, with a P0 baseline dashed line](/figures/crn-profit-by-rung.png)

## The idea

Imagine seven observers watching the exact same week unfold in the exact same store — the same customers walk in on the same days, the same trucks arrive carrying berries at the same true freshness, the same units spoil on the same flips of the coin. What differs between the seven is only which pair of glasses each one is wearing: one can only read the cash-register tape (rung P0, "books only"), another additionally gets a shrink-gun scan of what got thrown out (P1), another can trace which lot a sold unit came from (F1), and so on up to a rung that simply gets told the true state of every unit on the shelf (the oracle).

If instead each rung ran its *own* independently-randomized week, any profit difference you measured would be contaminated by ordinary Monte Carlo noise — one week just having fewer stockouts or less spoilage by chance — stacked on top of whatever the glasses actually bought a policy. Sharing the identical week's demand, spoilage, and true arrival freshness across every rung (a technique called common random numbers, or CRN) cancels that luck out. Whatever profit difference is left over is much closer to the pure effect of what each rung's filter could see.

## The math

The mechanism is a deterministic function from a small set of coordinates to a reproducible stream of random numbers, so that asking for the same coordinates twice — from Rust or from Python — always regenerates the identical draws, and different coordinates never collide. A draw is addressed by four pieces:

- $\text{root\_seed}$ — the top-level seed for one replication of the whole experiment,
- a run/tag label identifying *who* is drawing (the shared physics, or one particular rung's filter),
- $\text{day}$ — the calendar day within the episode,
- a stream name identifying *what kind* of randomness is being drawn (demand, spoilage, filter resampling, ...).

The reference implementation (`SpawnRng` in Rust, `spawn_rng` in Python) builds this address by hashing the four coordinates into an entropy pool and feeding it through NumPy's `SeedSequence` state-generation algorithm — reimplemented bit-for-bit in Rust so the two languages produce identical draws from the same coordinates, verified by a shared fixture (see the table below). Two different streams under the same $(\text{root\_seed}, \text{run}, \text{day})$ never interfere with each other: consuming many draws from one stream does not shift what the next draw from a different stream produces.

## Why it's modelled this way

ADR 0065 (SIM-02) makes the case for going further than pairing candidates *within* a rollout's inner loop (which the controller already required): since every knowledge rung differs only in **what a policy is allowed to observe**, never in the underlying physical process, the identical realization is valid to reuse across the *entire* knowledge ladder at a fixed $\beta$, not just across rollout candidates. That was adopted (option C, full CRN) over running the outer loop with no CRN at all (noisy, and reintroduces the same signal-to-noise problem CRN was built to solve for rollout) and over pairing policies only within one scenario/$\beta$ arm (less noise reduction, since it still lets different scenario arms drift apart on different physical draws).

ADR 0068 (SIM-05) is the addressing-scheme decision underneath that: a hierarchical SeedSequence spawn tree keyed by semantic slot — $(\text{run}, \text{day}, \text{stream})$ — rather than a single global RNG consumed sequentially. The rejected sequential alternative was flagged as dangerous specifically because it desyncs *silently*: the moment two arms draw a different number of random variates, their streams drift apart with no error and no visible symptom, just quietly worse decisions. A third alternative — pre-generating and storing every draw as arrays indexed by slot — was rejected only for its memory and storage cost across a full sweep, not on principle; ADR 0068 keeps it in reserve if a specific stream's reproducibility ever needs auditing by hand.

**Caveat — a real implementation split.** The NumPy-`SeedSequence`-compatible scheme described above (`SpawnRng` / `spawn_rng`) is what actually seeds the interactive Studio session, the controller's rollout, and alpha-tuning — and it is verified bit-identical to NumPy across languages by a shared cross-language fixture. The dedicated VOI CRN cell that produces the project's headline profit-by-rung numbers, `run_voi_crn_cell` in `voi.rs`, implements the *same architectural idea* — the same four coordinates, shared physics tag vs. per-rung filter tag — but through its own lighter-weight wrapping-multiply hash rather than by routing through `SpawnRng`; its own source comment flags this explicitly as "not NumPy-bit CRN." The pairing guarantee (same physics, different glasses) holds either way, but the two code paths do not produce byte-identical numbers from the same coordinates, and a reader should not assume the VOI cell's Rust streams equal what a NumPy `SeedSequence` call would produce for the same inputs.

## In the code

| Concept | Symbol | File:line |
| --- | --- | --- |
| Physics tag shared by every rung, every day | `physics_tag()` | `crates/voi_core/src/voi.rs:57` |
| Per-rung filter tag (only the filter's own randomness differs by rung) | `filter_tag(scenario)` | `crates/voi_core/src/voi.rs:61` |
| Demand draws (shared truth) | `STREAM_DEMAND` | `crates/voi_core/src/voi.rs:24` |
| Sales-allocation draws (shared truth) | `STREAM_ALLOC` | `crates/voi_core/src/voi.rs:25` |
| Gamma-aging draws (shared truth) | `STREAM_GAMMA` | `crates/voi_core/src/voi.rs:26` |
| Filter's own internal randomness (per-rung, not shared) | `STREAM_FILTER` | `crates/voi_core/src/voi.rs:31` |
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
- The filter's own resampling randomness (`STREAM_FILTER`) is deliberately tagged per-rung, not shared — each rung runs a differently-shaped filter (different rungs mask different observations), so only the underlying physical truth is meant to be shared, never the filter's internals.
- The production VOI CRN cell's seed-mixing function is a bespoke hash, not literally NumPy's `SeedSequence` algorithm (see the caveat above) — only the separate `SpawnRng` / `rng.py` primitive carries the verified bit-identical-to-NumPy guarantee.
- Getting the physics-tag-vs-filter-tag split wrong when adding a new rung — sharing a tag that should differ, or vice versa — would silently reintroduce the exact Monte Carlo noise this whole scheme exists to remove, with no error to flag the mistake.
