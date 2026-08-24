---
title: The studio, guided
sources:
  code: [web/src/react/StudioLayout.tsx, web/src/sections.ts, web/src/react/ObsControlsPane.tsx, web/src/controls.ts, web/src/paramLabels.ts, web/src/react/EventsPane.tsx, web/src/react/OperatorBar.tsx, web/src/react/studioLogic.ts, web/src/react/ReferenceDrawer.tsx]
---

# The studio, guided

The interactive studio is a single-page store simulator. It runs the same Rust engine as the notebooks and CLI, compiled to WebAssembly, driven day by day (or on Autopilot) from your browser. It lets you watch freshness, orders, and profit move together in real time: turn a knob, press Advance, and see the store react.

> **Figure (coming soon):** a full-page screenshot of the studio's cockpit grid — metrics column, belief column, sidebar, and tuning dock — annotated with the four zones named below.

## The idea

The studio is laid out in four zones on one screen. A **metrics column** across the top shows cumulative profit and loss, on-hand inventory by freshness band, and the day's order/spoilage/sales flow. Next to it, a **belief column** shows what the particle filter currently believes about freshness across the store — a freshness-over-time heatmap plus a panel showing the controller's inventory-vs-service tradeoff — with the day's run controls (order quantity, Advance, Autopilot, Reset) underneath. A narrow **sidebar** holds the observation-channel toggles (what the filter is allowed to see each day) and a rolling log of the last few days' deliveries, sales, and spoilage. Below all three, a full-width **tuning dock** holds every simulation knob, grouped into topic tabs (Demand, Arrival, Physics under "Sim params"; Logistics; Autopilot), with a small preview chart for whichever tab is open.

The knobs are not all equal weight. Each slider carries a colored tier badge showing what pressing it does: some change the picture instantly without touching the simulated days at all, some just preview what a future run would look like, and most require pressing **Reset** before they take effect, because they feed physics or demand draws that already happened in the current run.

## The math

The tier badges track one distinction: does a parameter affect the *sum over stored outcomes*, or does it feed the *simulation that produced those outcomes*?

Sell price $p_\text{sell}$, unit cost $c_\text{unit}$, waste cost $c_\text{waste}$, and stockout cost $c_\text{stockout}$ only ever appear in the profit-and-loss total:

$$
\text{Profit} = p_\text{sell} \cdot (\text{units sold}) - c_\text{unit} \cdot (\text{units purchased}) - c_\text{waste} \cdot (\text{units spoiled}) - c_\text{stockout} \cdot (\text{units missed})
$$

Units sold, purchased, spoiled, and missed are already fixed once a day has been simulated, so dragging any of those four prices just re-evaluates this sum over the same stored per-day counts — the charts update immediately with no re-simulation. That is a **Live** tier.

Everything else — reference life $\eta_\text{ref}$, the Q10 factor, reference and store temperature, picking selectivity, case size, lead time, base-stock target, arrival spread, transit temperature bias, and the random seed — feeds the freshness-decay integrand, the demand draw, or the arrival law itself (see [freshness, not age](/store/freshness-not-age) and [cold-chain arrival](/store/cold-chain-arrival)). Changing one without re-running the affected days would leave the displayed history inconsistent with the new setting, so the studio marks the run "dirty" and asks you to press Reset — a **Reset** tier. Mean daily demand $\mu$ sits in between: dragging it live-updates a *projected* demand chart (a **Preview**) without touching days already simulated, so you can see the effect of a candidate value before committing to a Reset.

## Why it's modelled this way

The sidebar's observation controls are three orthogonal toggles — code type (UPC vs. GSIN, i.e. whether POS scans resolve to a lot), scan-waste (on/off), and delivery history (none, pack date, or temperature history) — rather than a single dropdown of named presets. POS resolution, waste resolution, and delivery metadata are separate teaching levers, so dialing them independently is more informative than one combined choice. The named rungs (`P0`, `P1`, `F1`, `F1s`, `F2a`, `F2`, `F3` — see [the rung ladder](/ladder/rungs)) still exist as shorthand for particular channel combinations elsewhere in the app (the glossary, VOI sweeps), but the studio's live controls let you dial the three axes independently rather than only jumping between named points.

Autopilot reuses the same `act` request the manual **Place Order** button issues, on a repeating timer, rather than running a second in-browser heuristic loop. That way what you see Autopilot do is the same controller the notebooks and CLI can call, not a separate UI-only approximation.

The 90-day episode horizon is fixed rather than user-configurable: long enough that weekly demand and delivery-schedule patterns repeat a handful of times, short enough that a full particle-filter re-run after a Reset stays interactive.

**Caveat.** The tuning dock's visible tabs (Demand, Arrival, Physics, Logistics, Autopilot) are not the complete list of sections the studio code defines — `web/src/sections.ts` also defines `economics` and `pricing` sections with their own controls, reachable via the number-key shortcuts below, but neither currently has a clickable tab button in the tuning dock's cluster row. The Outcomes panel's P&L chart already surfaces the economics story, so this looks like a deliberate simplification rather than an oversight, but it wasn't possible to confirm that from the code alone.

## In the code

| Concept | Where | File:line |
| --- | --- | --- |
| Cockpit grid: metrics / belief / sidebar / tuning-dock zones | `cockpit-grid`, `cockpit-pane--metrics`, `cockpit-pane--belief`, `cockpit-pane--sidebar`, `cockpit-row--tuning` | `web/src/react/StudioLayout.tsx:44` |
| Freshness-over-time heatmap + controller tradeoff panel | `chart-history`, `belief-tradeoff-panel` | `web/src/react/StudioLayout.tsx:133`, `:162` |
| Run controls (order qty, Place Order, Autopilot, Reset) | `OperatorBar` | `web/src/react/OperatorBar.tsx:6` |
| Observation-channel toggles (code type, scan waste, delivery history) | `ObsControlsPane` | `web/src/react/ObsControlsPane.tsx:31` |
| Recent-events log (last 5 days: delivered / sold / spoiled) | `EventsPane` | `web/src/react/EventsPane.tsx:2` |
| Tuning-dock section list and per-tab blurb | `STUDIO_SECTIONS` | `web/src/sections.ts:20` |
| Slider update tiers (Live / Preview / Reset) | `ControlTier`, `PARAM_LABELS` | `web/src/paramLabels.ts:1`, `:9` |
| Tier badge render | `tierBadge` | `web/src/controls.ts:238` |
| Keyboard shortcuts: 1–7 jump to section, arrows step section | `onKeydown` | `web/src/react/studioLogic.ts:1305` |
| Keyboard shortcut `?` opens glossary/shortcuts/VOI-demo drawer | `ReferenceDrawer` | `web/src/react/ReferenceDrawer.tsx:26`, `:150` |

## Caveats

- The reference-drawer's **VOI** tab loads `/voi-reference.json`, a static demo stub the file itself labels "not live VOI computation" — it shows what a VOI table could look like, not a real value-of-information result from your current run. Treat any numbers there as placeholder formatting, not findings.
- Autopilot and manual paths share the same controller call, but the browser's particle-filter and rollout budgets (`n_particles`, `n_rollout_paths`, `H`, `candidate_case_radius`) are dialed down for interactive wall-clock speed and are not necessarily the same budgets a batch/notebook VOI sweep would use — treat studio numbers as illustrative of the mechanism, not as citeable VOI results.
- Panel names and tab groupings may change as the UI evolves; treat this page as a snapshot of the current build, not a permanent contract.
