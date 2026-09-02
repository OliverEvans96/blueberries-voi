---
title: What this is
sources:
  code: [crates/voi_core/Cargo.toml, crates/voi_py/Cargo.toml, crates/voi_wasm/Cargo.toml, web/package.json]
---

# What this is

This project asks one question: how much is better information about produce
freshness worth to a grocery store? Not "does a smarter sensor help" in the
abstract, but an actual number. We simulate a store that orders blueberries
every day, give it progressively richer ways to know what's actually on its
shelf, and compare the profit each way of knowing produces. That's a Value of
Information (VOI) study, and this site walks through how it's built and what
it currently finds.

::: info Rust API
The shared compute kernel is documented with **rustdoc** — API reference generated
from inline `///` comments on the Rust source, covering public functions, types,
and fields across `voi_core`, `voi_py`, and `voi_wasm`.

**[Open rustdoc →](/api/rust/index.html)**

For how rustdoc fits this narrative site, see
[Rust API (voi_core)](/reference/rust-api).
:::

## The idea

Three pieces do the work, and they all run on the same code. A Rust kernel
(`voi_core`) simulates the true physics of a shelf of blueberries — how fast each
berry loses freshness, when it spoils, who buys what. It separately runs a
*particle filter*: a population of guesses about the shelf's true freshness,
updated each day by whatever the store is actually allowed to observe. That
belief then drives an ordering policy, the same way a real store manager's
mental model of "how fresh is what's back there" drives how much they order
tomorrow.

The kernel is compiled two ways, so the same physics and the same filter run
everywhere the project needs them: natively via PyO3 (a Rust-to-Python bridge,
`voi_py`) for Python notebooks and offline experiments, and to WebAssembly
(code compiled to run directly in the browser, `voi_wasm`) for an in-browser
"studio" — a React + D3 app (`web/`) where you can watch a store run day by day
and change what it's allowed to see.

The "what it's allowed to see" part is the whole point. The site arranges each
level of observability into a five-rung knowledge ladder, from least to most
informative:

1. **Books only** — today's delivery and sales counts, what nearly every store already tracks.
2. **+ scan waste** — also scanning what got thrown out.
3. **+ pack date** — also knowing when each delivery was packed.
4. **+ LGTIN** — swapping the plain product barcode for an LGTIN, a lot-level identifier (a product's barcode plus a batch/lot number) that can tell one truckload of blueberries apart from another of the same product.
5. **+ temp. history** — also a logged temperature history for each shipment's trip to the store.

The central experiment reruns the same simulated weather and demand under each
rung of the ladder, so any difference in outcome is attributable to what the
store could see, not to which random day it happened to get.

## Why it's modelled this way

The alternative to simulating a store is fitting a closed-form inventory model
directly to whatever real data exists, and reasoning about the value of that
information analytically. That's not the approach here. Real cold-chain and
point of sale (POS) data for a comparison this granular — the same store, the
same days, several different knowledge states — doesn't exist, and it can't be
collected after the fact.

Simulating a store from first-principles physics solves that. A filter that
only sees what a given observation scenario would really expose can be run
using common random numbers (CRN) — the same underlying random draws — across
every scenario, so everything except what's observed is held fixed. That gives
a defensible answer. The cost of that choice is that every number on this site
is only as good as the physics and demand model underneath it — see the
caveats on the individual model pages for where those assumptions are weakest.

## In the code

| Concept | Crate / package | File |
| --- | --- | --- |
| Shelf physics, particle filter, ordering policy | `voi_core` | `crates/voi_core/Cargo.toml` |
| Native Python bindings | `voi_py` (`blueberries_voi._core`) | `crates/voi_py/Cargo.toml` |
| WebAssembly bindings for the browser studio | `voi_wasm` | `crates/voi_wasm/Cargo.toml` |
| In-browser studio (React + D3) | `@oliverevans96/blueberries-voi-studio` | `web/package.json` |

## Caveats

The headline result, in short, with full detail on the
[Findings](/findings/does-belief-sharpen) page: richer observation scenarios
steadily sharpen the filter's belief about shelf freshness. Across a 30-day
replay over 30 random seeds, adding pack date alone cuts belief error by more
than half compared to books-only — the belief W1 ratio (a measure of how far
the filter's belief is from the simulator's ground truth, the simulator's
actual true state as opposed to what the filter believes, scaled relative to
the books-only baseline) drops from 1.000 to 0.453. That's the single biggest
jump on the ladder. Adding LGTIN and then temperature history sharpens it
further, down to 0.214 at the top of the ladder — roughly 4.7× sharper than
books-only overall.

What that sharper belief does not do, in this experiment, is turn into more
profit. Closed-loop profit — profit when the ordering policy is actually
placing orders, rather than just being tested against a fixed order schedule —
lands within about 1% of the books-only baseline in every scenario on the
ladder. That's a settled result, not seed-to-seed noise. The likely reason is
that the ordering policy is short-sighted: it only optimizes over the next few
days of demand and freshness, not blueberries' roughly 10-day shelf life, so it
can't fully exploit a sharper belief. The economics reinforce this — missing a
sale costs roughly $5.20 (a stockout penalty plus the forgone profit margin)
versus $1.20 to waste a spoiled unit, about 4.3× worse — so a policy that
already leans toward over-ordering is close to profit-maximizing even with a
coarse belief. Two other controller designs were tried as well, and neither
improved profit meaningfully, which points to the ordering policy rather than
to the value of the information itself. That gap between "we can see more
clearly" and "we haven't shown it pays" is explored further on the Findings
pages; this page is just the short summary up front.
