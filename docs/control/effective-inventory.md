---
title: Effective inventory
sources:
  adr: [130]
  code: [crates/voi_core/src/policy.rs, src/blueberries_voi/filter/belief.py, web/src/charts/inventoryTarget.ts]
---

# Effective inventory

Before the store can decide how much to order, it needs one number that answers "how much protection against running out do I already have?" Just counting units on the shelf overstates that protection, because a unit that's nearly spoiled barely helps tomorrow's customers. **Effective inventory**, $\tilde I$, is that number done right: every unit counted in proportion to how much sellable life it has left, not as a flat $1$.

> **Figure (coming soon):** a bar chart of one shelf's lots (raw unit counts) next to the same lots re-weighted by expected freshness, showing the two totals diverge as the shelf skews toward less-fresh stock.

## The idea

Picture two shelves, each with 10 units. Shelf A's units are all freshly delivered — freshness $f$ near 1 for every unit. Shelf B's units have been sitting for a while — freshness $f$ near 0.2, close to spoiling. Both shelves report "10 units on hand," but they do not offer the same protection against a busy day: Shelf B's units will mostly be gone (sold or spoiled) well before Shelf A's would be. A policy that orders based on raw unit counts would treat these two shelves identically and under-order for Shelf B.

Effective inventory fixes this by weighting each unit by its expected freshness before adding it to the total. A lot of 10 units with mean freshness 0.5 contributes $10 \times 0.5 = 5$ "pristine-equivalent units," not 10. Units still in the delivery pipeline — ordered but not yet arrived — get counted too, but conservatively: since the model doesn't yet know their exact freshness on arrival, they're assumed to show up at a fixed default freshness (in practice, treated as arriving pristine, $f_{\text{pipe}} = 1$, for planning purposes).

## The math

The belief the store holds about its shelf is a set of $L$ lots, each with a histogram over freshness bins. For lot $\ell$, $n_\ell$ is the expected number of alive units in that lot, and $p_{\ell k}$ is the probability mass the belief places on freshness bin $k$ (bin center $f_k \in [0,1]$). The lot's expected freshness is

$$
\mathbb{E}[f \mid \ell] = \sum_{k=1}^{K} p_{\ell k}\, f_k \,.
$$

Effective inventory sums the quality-weighted on-hand stock across all $L$ lots, plus a pipeline term for units already ordered ($q_{\text{pipeline}}$) but not yet delivered:

$$
\tilde I = \sum_{\ell=1}^{L} n_\ell \, \mathbb{E}[f \mid \ell] \;+\; q_{\text{pipeline}} \, f_{\text{pipe}} \,.
$$

**Worked example.** Two lots: lot 1 has $n_1 = 10$ units at mean freshness $0.5$; lot 2 has $n_2 = 5$ units at mean freshness $1.0$. On-hand contribution is $10 \times 0.5 + 5 \times 1.0 = 10$. With $8$ units pending delivery at the default pipeline freshness $f_{\text{pipe}} = 1.0$, the pipeline adds $8$. Total: $\tilde I = 18$ — the shelf-plus-pipeline protects against demand as if it held 18 perfectly fresh units, even though 23 physical units are involved across both terms.

The weighting used per unit is formally a **quality weight** $w(f) = \mathbb{E}[T_{\text{remaining}} \mid f] / T_{\text{nominal}}$ — the fraction of a pristine unit's expected remaining sellable life that a unit at freshness $f$ still has. Under a **deterministic** daily freshness decrement, remaining life is exactly linear in $f$, so $w(f) = f$ exactly. The formula above uses $w(f_k) = f_k$ at each bin center — i.e., it treats the freshness value itself as the quality weight.

## Why it's modelled this way

ADR 0130 locked a single, unit-level freshness coordinate $f$ end-to-end: ground truth, the particle filter's internal state, the belief wire, and the ordering policy all speak $f$ directly, with **no Weibull survival model** on the production hot path. Effective inventory used to be defined as a Weibull survival integral over an age-clock (τ) histogram exported by the filter; once the filter itself went unit-freshness-native, that definition no longer matched what the filter actually tracked. The ADR's own accounting of the rejected alternative is direct: keeping a Weibull-over-τ effective-inventory calculation while the filter emits $f$-histograms was rejected because it "breaks unified truth" — $\mathbb{E}[f]$ is the direct sufficient statistic for the ordering rule once unit state is $f$ itself. The old τ/Weibull effective-inventory path is retired to a legacy/research path, not used by production ordering.

**Honest caveat.** Using $w(f_k) = f_k$ is exact only in the deterministic-decrement case. The production model's actual in-store aging is a **stochastic gamma** process, not a deterministic one, and under stochastic aging $w(f)$ is only *first-order* correct as $w(f) \approx f$ — Jensen's-inequality and first-passage-time effects mean the true expected-remaining-life fraction isn't perfectly linear in $f$ in general. The shipped version uses $w(f_k) = f_k$ anyway, because it matches the deterministic-gamma physics exactly, needed no new numerics to ship, and is close under the actual stochastic dynamics. A more exact $w(f_k)$, computed via Monte Carlo simulation or a first-passage-time approximation on the actual gamma aging parameters, is a documented follow-up refinement, not shipped code.

## In the code

| Concept | Symbol | File:line |
| --- | --- | --- |
| Effective inventory (Rust) | $\tilde I$ | `crates/voi_core/src/policy.rs:179` ([`effective_inventory_f_belief`](/api/rust/voi_core/policy/fn.effective_inventory_f_belief.html)) |
| Effective inventory (Python) | $\tilde I$ | `src/blueberries_voi/filter/belief.py:131` (`effective_inventory`) |
| Effective inventory (TypeScript, studio charts) | $\tilde I$ | `web/src/charts/inventoryTarget.ts:99` (`effectiveInventoryFromFlatBelief`) |
| Per-lot expected freshness loop | $\mathbb{E}[f \mid \ell] = \sum_k p_{\ell k} f_k$ | `crates/voi_core/src/policy.rs:189-196` (inline accumulation inside `effective_inventory_f_belief`) |
| Lot counts (expected alive units per lot) | $n_\ell$ | `crates/voi_core/src/policy.rs:180` (`lot_counts` parameter) |
| Freshness histogram (bin masses, bin centers) | $p_{\ell k}$, $f_k$ | `crates/voi_core/src/policy.rs:181-182` (`f_marginals`, `f_grid` parameters) |
| Pipeline term | $q_{\text{pipeline}} \, f_{\text{pipe}}$ | `crates/voi_core/src/policy.rs:183-184, 197` (`pending_sum`, `f_pipeline_default`) |

## Caveats

- The shipped $w(f_k) = f_k$ weighting is exact only under deterministic decrement; under the model's actual stochastic gamma aging it's a first-order approximation (see the honest caveat above). A tabulated, more exact $w(f_k)$ via Monte Carlo or first-passage approximation exists only as a documented follow-up, not shipped code.
- $\mathbb{E}[f \mid \ell]$ is a first moment only — two lots with the same mean freshness but very different spread (one tightly clustered near the mean, one split between nearly-pristine and nearly-spoiled units) contribute identically to $\tilde I$ even though their near-term spoilage risk differs.
- Pipeline units are counted at one fixed default freshness ($f_{\text{pipe}}$, typically $1.0$) rather than their own predicted arrival-freshness distribution — the model doesn't yet vary the pipeline weight by how far along the delivery is or what corridor it's coming from.
- Effective inventory only sums over the lots present in the belief wire's $L$-lot window (see the [glossary](/start-here/glossary) for the default $L$); a shelf with unusually long-lived stock beyond that window would not have every physical lot represented in $\tilde I$.
