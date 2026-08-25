---
title: What one particle is
sources:
  code: [crates/voi_core/src/unit_pf.rs]
---

# What one particle is

The [previous page](/inference/why-particle-filter) argued that the filter should track its belief as a crowd of complete hypothetical shelves rather than a single smooth summary. This page looks at what a single member of that crowd — one particle — actually stores, and how the crowd is laid out in memory so that hundreds of them can be updated every simulated day.

![Three particles as shaded shelves: same lot widths, different freshness shading](/figures/particle-shelf-shading.png)

## The idea

A particle is a full, concrete guess at "here is exactly what's on the shelf right now": one freshness number for every unit that particle believes is alive, grouped into the lots (deliveries) they arrived in. The filter keeps a bank of many such particles side by side — by default 200 of them — each carrying its own opinion about how fresh every unit is, and its own weight (how much the filter currently trusts that guess).

One thing is *not* uncertain across the bank: how many units are in each lot, and where each lot's units sit in the layout. A delivery's size is read off the truck manifest — it's a count on the wire, not something the filter has to infer — so every particle agrees on it. Deliveries are appended to the bank as a new *segment*: a contiguous stretch of slots exactly as wide as that delivery, the same width in every particle. What the particles disagree about, and what the filter is actually trying to learn, is only the *freshness* sitting in those slots — which units within a lot are still crisp and which are closer to spoiled. So a lot's quantity is shared, fixed structure; a lot's freshness values are the private, particle-specific state.

Practically, this shared segmentation is also what makes lot-resolved observations (a per-lot waste count, a scanned lot ID) meaningful: because every particle already agrees on which slots belong to which lot, a lot-resolved reading can be matched to the right segment by lot identity rather than guessed at from row position.

## The math

For a bank of $N$ particles, particle $i$ carries a freshness vector

$$
f^{(i)} = \left(f^{(i)}_1, \dots, f^{(i)}_{M}\right), \qquad f^{(i)}_j \in [0, 1]
$$

where $M$ is the current number of live-or-dead slots on the shelf (it grows by one delivery's width on each arrival). This vector is partitioned into $L$ lot segments by a set of offsets

$$
0 = o_0 < o_1 < \dots < o_L = M
$$

shared identically across every particle $i = 1, \dots, N$: lot $\ell$ occupies slots $o_{\ell-1}+1, \dots, o_\ell$ in *every* particle's vector, and each segment carries a lot identity (an id from the arrival stream, or a synthetic one when lot identity isn't observed). A unit is alive if its freshness is strictly positive and dead once $f^{(i)}_j \le 0$; the alive count in lot $\ell$ for particle $i$ is

$$
\#\left\{\, j \in (o_{\ell-1}, o_\ell] : f^{(i)}_j > 0 \,\right\}
$$

Because the offsets $o_0, \dots, o_L$ and lot ids do not carry a particle index $i$, arrival quantity is exact and identical across the whole bank — the only quantity that varies by $i$ is the freshness content inside each segment. Each particle also carries a scalar weight $w^{(i)}$, normalized so $\sum_i w^{(i)} = 1$, reflecting how well that particle's freshness story has matched the observations so far.

## Why it's modelled this way

Sharing the lot segmentation across particles, rather than letting each particle infer its own boundaries, is a deliberate simplification: delivery quantity is treated as directly observed truck-manifest data, not as something worth spending particle diversity on. Units within a lot age and spoil individually — each live unit draws its own daily decrement, rather than a single shared decrement for the whole lot — while the observed segmentation itself stays shared.

**Alternative considered: let each particle guess its own lot boundaries** (re-derive them from row length, or free-running per-particle segmentation). Guessed boundaries drift apart from the true delivery boundaries over an episode, so the lot-resolved observation channel would end up scoring the wrong slots against the wrong evidence, degrading it toward an uninformative bootstrap filter. Tying every particle to one observed segmentation, built directly from the arrival stream, avoids that.

**Alternative considered: start particles pre-filled with plausible inventory.** Every particle bank and the physical shelf both start empty instead, with inventory entering only through observed arrivals — pre-filling would produce persistent "phantom" belief mass that doesn't correspond to anything the store actually received.

**Caveat:** because arrival quantity is shared and only freshness is stochastic per particle, the filter is structurally unable to represent uncertainty about *how many* units arrived — if that number is ever wrong on the wire (a miscount, a data error), no particle in the bank can express doubt about it. That's a deliberate trade: a much simpler and faster filter, in exchange for treating delivery counts as ground truth.

## In the code

| Concept | Symbol / name | File:line |
|---|---|---|
| The particle bank itself | `UnitParticleBank` struct | `crates/voi_core/src/unit_pf.rs:51` |
| Per-particle weight | `weights: Vec<f64>` | `crates/voi_core/src/unit_pf.rs:52` |
| Per-particle freshness vector $f^{(i)}$ | `freshness: Vec<Vec<f64>>` | `crates/voi_core/src/unit_pf.rs:53` |
| Shared lot segment boundaries $o_0,\dots,o_L$ | `lot_offsets: Vec<usize>` | `crates/voi_core/src/unit_pf.rs:55` |
| Shared lot identities | `lot_ids: Vec<i64>` | `crates/voi_core/src/unit_pf.rs:57` |
| Zero-init constructor (empty bank) | `UnitParticleBank::empty` | `crates/voi_core/src/unit_pf.rs:62` |
| Number of lots currently tracked | `UnitParticleBank::n_lots` | `crates/voi_core/src/unit_pf.rs:87` |
| Appending one delivery as a new shared segment | `push_lot_births` | `crates/voi_core/src/unit_pf.rs:109` |

## Caveats

This page describes the state's *layout*, not how it's updated day to day (aging, sales, spoilage scoring) — that's covered on the filter-step page. It also doesn't cover how a unit's initial freshness is drawn at birth (the arrival model), only how the resulting values are organized once a delivery lands in the bank. And as noted above, the shared-segmentation design means arrival *quantity* is out of scope for what this filter can express uncertainty about — only arrival *freshness* is.
