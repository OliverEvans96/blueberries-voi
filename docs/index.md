---
title: What this is
sources:
  adr: [0119, 0144]
  code: [crates/voi_core/Cargo.toml, crates/voi_py/Cargo.toml, crates/voi_wasm/Cargo.toml, web/package.json]
---

# What this is

This project asks one question: **how much is better information about produce
freshness worth to a grocery store?** Not "does a smarter sensor help" in the
abstract, but a number — measured by simulating a store that orders blueberries
every day, giving it progressively richer ways to know what's actually on its
shelf, and comparing the profit each way of knowing produces. That's a
value-of-information (VOI) study, and this site is the walkthrough of how it's
built and what it currently finds.

![Filter accuracy improves sharply as the store's observation channel gets richer, from books-only (P0) down to a full temperature trace (F3)](/figures/accuracy-ladder-mae-f.png)

## The idea

Three pieces do the work, and they all run on the same code. A Rust kernel
(`voi_core`) simulates the true physics of a shelf of blueberries — how fast they
age, when they spoil, who buys what — and separately runs a *particle filter*: a
population of guesses about the shelf's true freshness, updated each day by
whatever the store is actually allowed to observe. That belief then drives an
ordering policy, the same way a real store manager's mental model of "how fresh is
what's back there" drives how much they order tomorrow. The kernel is compiled two
ways so the same physics and the same filter run everywhere the project needs
them: natively via PyO3 bindings (`voi_py`) for Python notebooks and offline
experiments, and to WebAssembly (`voi_wasm`) inside an in-browser "studio" — a
React + D3 app (`web/`) where you can watch a store run day by day and change what
it's allowed to see.

The "what it's allowed to see" part is the whole point. The site calls each preset
level of observability a **rung** on a knowledge ladder — from `P0` (books only:
today's sales and waste totals) up through `F3` (a full cold-chain temperature
trace on every shipment) — and the central experiment reruns the *same* simulated
weather and demand under each rung, so any difference in outcome is attributable
to what the store could see, not to which random day it happened to get.

## Why it's modelled this way

The alternative to simulating a store is fitting a closed-form inventory model
directly to whatever real data exists and reasoning about information value
analytically. That's rejected here on purpose: real cold-chain and point-of-sale
data for a comparison this granular — the same store, the same days, seven
different knowledge states — doesn't exist and can't be collected retroactively.
Simulating a store from first-principles physics, with a filter that only sees
what a given rung would really expose, is the only way to hold "everything except
what's observed" fixed and still get a defensible answer. The honest cost of that
choice is that every number on this site is only as good as the physics and demand
model underneath it — see the caveats on the individual model pages for where
those assumptions are weakest.

## In the code

| Concept | Crate / package | File |
| --- | --- | --- |
| Shelf physics, particle filter, ordering policy | `voi_core` | `crates/voi_core/Cargo.toml` |
| Native Python bindings | `voi_py` (`blueberries_voi._core`) | `crates/voi_py/Cargo.toml` |
| WebAssembly bindings for the browser studio | `voi_wasm` | `crates/voi_wasm/Cargo.toml` |
| In-browser studio (React + D3) | `@oliverevans96/blueberries-voi-studio` | `web/package.json` |

## Caveats

Here's the headline result stated plainly, with the detail left for the
[Findings](/findings/does-belief-sharpen) section: sharper observation rungs
sharpen the filter's belief about arrival freshness *a lot* — on a recent replay,
mean |belief − truth| on shelf freshness drops roughly **6×** from the
books-only rung to the full temperature-trace rung. What that sharper belief has
**not** yet reliably done, at the experiment budgets run so far, is translate into
more profit — closed-loop profit under the current ordering policy still moves
more with which random seed you happen to draw than with which rung the store is
on. That gap between "we can see much more clearly" and "we haven't yet proven it
pays" is explored in full on the Findings pages; this page is just the honest
one-line summary up front.
