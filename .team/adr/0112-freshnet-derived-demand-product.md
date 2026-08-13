# 0112. FreshNet derived demand product (Track B)

STATUS: ACCEPTED
DATE: 2026-08-13
BOARD-ID: CAL-B1
GROUP: CAL
PROVENANCE: CAL-01 Wave 0
TIER: 1
MILESTONE: CAL-01 — calendar realism

## Context

CAL-01 needs calendar DOW×week demand structure ([0110](./0110-mod-09-calendar-demand.md)) without
pulling Hugging Face / `datasets` / raw parquet into runtime or Pyodide. The Abdella pattern
(derived product + PROVENANCE + optional desktop extra) already works for arrivals.

Source: [FreshRetailNet-50K](https://huggingface.co/datasets/Dingdong-Inc/FreshRetailNet-50K)
(`Dingdong-Inc/FreshRetailNet-50K`, CC BY 4.0; paper [arXiv:2505.16319](https://arxiv.org/abs/2505.16319)).
~90 days Mar–Jun 2024; categories are opaque IDs; `sale_amount` is globally normalized.

## Decision

We will ship a **committed derived demand product** and keep HF out of runtime:

1. **Offline ingest / fit only** via optional `[freshnet]` extra (`datasets` / HF hub deps). Not a
   core or browser dependency of `blueberries_voi`.
2. **Artifacts under `data/freshnet/`:**
   - `PROVENANCE.md` — dataset id, license, download date/commit, SKU selection rule + selected IDs,
     censoring rule, scale rule, seasonality honesty, China blueberry transferability (below).
   - `demand_profile.json` — day-of-week × week-index (or month) mean multipliers / μ(day) table,
     dispersion, scale factor to operational μ≈30, schema version.
3. **SKU selection (reproducible):** prefer fruit / high-velocity perishable `management_group`
   subset when IDs allow; else pool documented fresh SKUs. Commit the exact ID list in
   `PROVENANCE.md`. Categories have no blueberry label — selection is rule-based, not name match.
4. **Scale:** fit **relative** DOW/season shape; multiply so mean operational demand ≈ **30**
   (MOD-26 continuity). Do **not** treat normalized Chinese `sale_amount` as punnets or transfer
   yuan prices into `ProfitCosts`.
5. **Censoring:** prefer days with low/zero `stock_hour6_22_cnt` for MLE / mean estimation; full
   paper two-stage latent recovery is **optional v2**, not blocking CAL-01.
6. **Seasonality depth honesty:** “seasonal” means DOW + week-index factors over the Mar–Jun
   window only. Full annual seasonality is out of sample until more data exists.
7. **Runtime:** package loader reads JSON only (mirror Abdella product). Physics / CRN never import
   HF.
8. **Ownership:** Track B owns `model/demand*` + `data/freshnet/` + fit/ingest scripts.

### China blueberry transferability (binding honesty for the post)

Blueberries are **not rare** in China today and are **no longer a luxury rarity**, but they remain a
**premium, high-velocity berry** with distinctive seasonality — not a staple like leafy greens.

| Fact | Implication for CAL-01 |
|------|------------------------|
| China is the world’s #1 producer by area/output; Yunnan + northern greenhouse stagger supply toward near year-round availability | FreshNet Mar–Jun sits in **peak domestic season** — DOW/season shape from that window is blueberry-relevant, not off-season import-only |
| Retail packs often ~20–30 yuan / 125–250 g in season; historically much more expensive | Absolute Chinese unit prices are **not** transferable to US/EU VOI economics; keep `ProfitCosts` / μ≈30 as model knobs; borrow **shape** (DOW, censoring, stockout) not yuan |
| Still more aspirational than commodity vegetables; promo- and holiday-sensitive | Prefer fruit/berry-like subset; expect sharper weekend/holiday spikes than staples |
| Dingdong treats blueberries as a signature fruit in-channel | Blueberries are **in-channel** for this retailer — not an exotic missing category |
| FreshNet is front-warehouse / instant-delivery e-commerce, not Western DC→store MWF trucks | Transfer calendar structure **cautiously**; DOW may reflect app ordering + same-day fulfillment |
| Chinese holidays in Mar–Jun ≠ Western calendar | Holiday flags are covariates or absorbed into week factors — **not** mapped 1:1 onto the US episode calendar |

**Bottom line:** Chinese fresh-retail data is scientifically fine for **perishable demand cyclicity
and censoring**. Do **not** claim FreshNet calibrates Western blueberry **price**, **pack size**, or
**store delivery logistics**.

## Alternatives considered

- **HF / `datasets` as a runtime dependency** — rejected: breaks Pyodide / slim wheel and couples
  citeable draws to network I/O.
- **Keep i.i.d. and skip FreshNet** — rejected: Oliver locked FreshNet for CAL-01 shape.
- **Full two-stage latent demand recovery as v1 prior** — rejected: optional follow-up; censoring
  filter on low stockout hours is enough for CAL-01.
- **Map Chinese holidays onto US episode dates** — rejected: calendars differ; absorb into week
  factors / covariates instead.
- **Use FreshNet yuan or normalized sales as economic units** — rejected: economics stay scenario
  knobs at μ≈30 / existing `ProfitCosts`.

## Consequences

**Easy:** browser and CI load a small JSON; provenance is auditable; shape is citeable.

**Hard / cost:** SKU opacity and normalized sales force honesty footnotes; Mar–Jun ≠ annual;
ingest/fit scripts and `[freshnet]` extra must stay out of the slim import graph.

**Locked in:** derived JSON product; optional `[freshnet]` for fit only; scale-to-μ≈30; no HF in
runtime; transferability paragraph above.

**Revisit if:** a longer public fresh series lands, or Oliver wants two-stage latent recovery as the
production prior.
