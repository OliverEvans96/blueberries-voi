---
title: The studio, guided
sources:
  code: [web/src/react/StudioLayout.tsx, web/src/sections.ts, web/src/react/ObsControlsPane.tsx, web/src/controls.ts, web/src/paramLabels.ts, web/src/react/EventsPane.tsx, web/src/react/OperatorBar.tsx, web/src/react/studioLogic.ts, web/src/react/ReferenceDrawer.tsx, web/src/charts/beliefAccuracy.ts]
---

# The studio, guided

The interactive studio is a single-page store simulator. It runs the same Rust engine as the notebooks and CLI, compiled to WebAssembly, driven day by day (or on Autopilot) from your browser. It lets you watch freshness, orders, and profit move together in real time: turn a knob, press Advance, and see the store react.

## The idea

The studio is laid out in three zones on one screen. A **metrics column** on the left shows cumulative profit and loss and the day's order/spoilage/sales flow. Next to it, a **belief column** shows what the particle filter currently believes about freshness across the store — a freshness-over-time heatmap — with the day's run controls (order quantity, Place Order, Autopilot, Reset) above it.

When Omniscience is on, a small **belief accuracy** table under today's freshness histogram shows how far the filter's belief sits from the truth. Three numbers make up the table. **Freshness (mean)** is the Mean Absolute Error (MAE) — the average size of the gap, ignoring direction — between the filter's guess at the shelf's average freshness and the true average. **Freshness (distribution)** uses the 1-Wasserstein distance (W1) — a measure of how far apart two distributions are — comparing the filter's whole belief about freshness across every unit to the true spread, on the same eight display bins the histogram above it uses. **Count** is simply the difference between how many units the filter expects to be on the shelf and how many actually are. **Today** shows that day's score; **All days** averages the daily scores across the whole run — for the distribution column, that means averaging each day's W1 value, not recomputing one W1 distance over every day's units lumped together.

A narrow **sidebar** holds the observation-channel toggles (what the filter is allowed to see each day) and a rolling log of the last few days' deliveries, sales, and spoilage. A **tuning dock** drawer, opened from a button in the title bar, holds every simulation knob, grouped into topic tabs (Demand, Arrival, Physics under "Sim params"; Logistics; Autopilot), with a small preview chart for whichever tab is open.

The knobs are not all equal weight. Each slider carries a colored tier badge showing what pressing it does: some change the picture instantly without touching the simulated days at all, some just preview what a future run would look like, and most require pressing **Reset** before they take effect, because they feed physics or demand draws that already happened in the current run.

## The math

The tier badges track one distinction: does a parameter affect the *sum over stored outcomes*, or does it feed the *simulation that produced those outcomes*?

Sell price $p_\text{sell}$, unit cost $c_\text{unit}$, waste cost $c_\text{waste}$, and stockout cost $c_\text{stockout}$ only ever appear in the profit-and-loss total:

$$
\text{Profit} = p_\text{sell} \cdot (\text{units sold}) - c_\text{unit} \cdot (\text{units purchased}) - c_\text{waste} \cdot (\text{units spoiled}) - c_\text{stockout} \cdot (\text{units missed})
$$

Units sold, purchased, spoiled, and missed are already fixed once a day has been simulated, so dragging any of those four prices just re-evaluates this sum over the same stored per-day counts — the charts update immediately with no re-simulation. That is a **Live** tier.

Everything else changes how a day gets simulated in the first place, not just how the results are added up afterward. That list includes the reference shelf life $\eta_\text{ref}$, the Q10 factor — an Arrhenius-style rule from food science, where spoilage roughly multiplies by Q10 for every 10°C rise in temperature — reference and store temperature, picking selectivity, case size, lead time, arrival spread, transit temperature bias, and the random seed. These feed the freshness-decay math, the demand draw, or how deliveries arrive (see [freshness, not age](/store/freshness-not-age) and [cold-chain arrival](/store/cold-chain-arrival)). Changing one of them without re-running the affected days would leave the displayed history inconsistent with the new setting. So the studio marks the run "dirty" and asks you to press Reset — a **Reset** tier. Mean daily demand $\mu$ sits in between: dragging it live-updates a *projected* demand chart (a **Preview**) without touching days already simulated, so you can see the effect of a candidate value before committing to a Reset.

## Why it's modelled this way

The sidebar's observation controls are three independent toggles, not a single dropdown of named presets: **code type** — Universal Product Code (UPC) versus LGTIN (a barcode that identifies one specific delivery batch, not just the product), i.e. whether a scan at the point of sale (POS) can be traced back to a particular lot rather than just a product — whether **waste scanning** is on (scanning spoiled units as they're thrown out, rather than only inferring waste from the books), and **delivery history** (none, pack date, or temperature history). POS resolution, waste-scan resolution, and delivery metadata are separate teaching levers, so dialing them independently is more informative than one combined choice. Named observation scenarios (see [the observation scenarios](/ladder/observation-scenarios)) still exist elsewhere in the app — the glossary, Value of Information (VOI) sweeps — as shorthand for particular combinations of these toggles, but the studio's live controls let you dial the three axes independently rather than only jumping between named points.

Autopilot reuses the same ordering request the manual **Place Order** button issues, on a repeating timer, rather than running a second in-browser heuristic loop. That way what you see Autopilot do is the same controller the notebooks and CLI can call, not a separate UI-only approximation.

The 90-day episode horizon is fixed rather than user-configurable: long enough that weekly demand and delivery-schedule patterns repeat a handful of times, short enough that a full particle-filter re-run after a Reset stays interactive.

**Caveat.** The tuning dock's visible tabs (Demand, Arrival, Physics, Logistics, Autopilot) aren't the complete list of sections defined in the code. Two more sections — economics and pricing — exist and are reachable via the number-key shortcuts below, but they don't yet have a clickable tab button in the dock's row of tabs. The Outcomes panel's profit and loss (P&L) chart already covers the economics story elsewhere in the studio, so this is a deliberate simplification, not a missing feature.

## In the code

| Concept | Where | File:line |
| --- | --- | --- |
| Cockpit grid: metrics / belief / sidebar zones | `cockpit-grid`, `cockpit-pane--metrics`, `cockpit-pane--belief`, `cockpit-pane--sidebar` | `web/src/react/StudioLayout.tsx:123` |
| Freshness-over-time heatmap | `chart-history` | `web/src/react/StudioLayout.tsx:311` |
| Belief accuracy table (mean-f MAE, freshness W₁, count MAE) | `data-belief-mae-table`, `countMeanAbsError`, `currentFreshnessW1`, `meanFreshnessW1OverHistory`, `meanCountMaeOverHistory` | `web/src/react/StudioLayout.tsx:329`, `web/src/charts/beliefAccuracy.ts:102`, `:187`, `:222`, `:327` |
| Run controls (order qty, Place Order, Autopilot, Reset) | `OperatorBar` | `web/src/react/OperatorBar.tsx:6` |
| Observation-channel toggles (code type, scan waste, delivery history) | `ObsControlsPane` | `web/src/react/ObsControlsPane.tsx:31` |
| Recent-events log (last 5 days: delivered / sold / spoiled) | `EventsPane` | `web/src/react/EventsPane.tsx:2` |
| Tuning-dock section list and per-tab blurb | `STUDIO_SECTIONS` | `web/src/sections.ts:20` |
| Slider update tiers (Live / Preview / Reset) | `ControlTier`, `PARAM_LABELS` | `web/src/paramLabels.ts:1`, `:9` |
| Tier badge render | `tierBadge` | `web/src/controls.ts:238` |
| Keyboard shortcuts: 1–7 jump to section, arrows step section | `onKeydown` | `web/src/react/studioLogic.ts:1305` |
| Keyboard shortcut `?` opens glossary/shortcuts/VOI-demo drawer | `ReferenceDrawer` | `web/src/react/ReferenceDrawer.tsx:26`, `:150` |

## Caveats

- The reference drawer's **VOI** tab loads a static demo file that's labeled, in the file itself, as "not live VOI computation" — it shows what a VOI table could look like, not a real value-of-information result from your current run. Treat any numbers there as placeholder formatting, not findings.
- Autopilot and manual ordering share the same controller call, but the browser dials down how many particles the filter tracks and how far ahead the planner looks, to keep things fast enough to feel interactive. Those budgets aren't necessarily the same ones a batch or notebook VOI sweep would use, so treat studio numbers as illustrating the mechanism, not as citable VOI results.
- The **All days** score is an average of each day's own **Today** score — it doesn't recompute a single W1 distance across every unit from every day lumped together. That's the same way the freshness-mean MAE column is averaged, and it keeps unusual days (right after a restock, or when the shelf runs empty) from being blended into one number that doesn't represent any single day well.
- The studio only sends the browser a single expected count per lot, averaged across all of the filter's particles — not each particle's own separate guess. Notebooks that keep every particle's guess can score the whole predictive count using the Continuous Ranked Probability Score (CRPS) — a measure of how well a full predictive distribution, not just its mean, matches what actually happened. The studio can't compute that from the single averaged number it receives, so it only shows the freshness mean MAE and freshness W1 scores described above — there's no separate count-CRPS score in the studio.
- Panel names and tab groupings may change as the UI evolves; treat this page as a snapshot of the current build, not a permanent contract.
