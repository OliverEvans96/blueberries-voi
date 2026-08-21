/** Studio runtime (T-121) — logic migrated from main.ts; shell in StudioLayout.tsx. */
import { createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { flushSync } from "react-dom";
import { bindDemandSliderPreview } from "../engine/demandPreview";
import { arrivalRugAvailable } from "../scenarioAvailability";
import { channelsCacheKey, channelsForPreset } from "../obsMask";
import { ViewModelProjector } from "../engine/projector";
import {
  applyEngineStatusChip,
  createEngineStatusTracker,
} from "../engine/engineStatus";
import {
  createStudioAdapter,
  reportStudioAdapterError,
  resolveStudioAdapterKind,
  studioFooterCopy,
  type StudioEnv,
} from "../engine/studioAdapter";
import {
  renderBeliefFreshnessTime,
  setBeliefFreshnessTimeHover,
} from "../charts/beliefFreshnessTime";
import {
  freshnessHistogramDataFromFlat,
  renderFreshnessHistogram,
} from "../charts/freshnessHistogram";
import {
  marginalYMax,
  renderMarginal,
  renderWasteBars,
  setMarginalHover,
  setWasteBarsHover,
  wasteBarYMax,
} from "../charts/marginals";
import { renderDemandDist } from "../charts/demandDist";
import {
  ageCompositionSeries,
  ageCompositionSeriesFromBelief,
  inventorySeries,
  inventorySeriesFromBelief,
  renderAgeComposition,
  renderInventoryTarget,
} from "../charts/inventoryTarget";
import { renderControllerOrders } from "../charts/controllerOrders";
import { renderSalesDemand, setSalesDemandHover } from "../charts/salesDemand";
import {
  renderArrivalPrior,
  renderArrivalShift,
} from "../charts/arrivalPrior";
import {
  renderArrheniusTemp,
  renderGammaFreshnessPath,
} from "../charts/physicsTeaching";
import {
  controlsFromVm,
  DEFAULT_CONTROLLER_CONTROLS,
  EPISODE_HORIZON,
  mountSectionControls,
  type ControllerControlsState,
} from "../controls";
import { createAutopilotLoop } from "../autopilotLoop";
import { attachLinkedHover, type HoverPoint } from "../hoverLink";
import {
  STUDIO_SECTIONS,
  loadSection,
  saveSection,
  type SectionId,
} from "../sections";
import type { Economics, HoverDay, ObsChannels, ScenarioId, SimConfig, ViewModel } from "../types";
import type { ActOpts, ScheduleWire, Snapshot } from "../engine/types";
import { buildStepNOrders, previousOrderDayFromSchedule } from "../calendar/nextOrderAdvance";
import { loadShowTruth, saveShowTruth } from "../showTruth";
import type { EventDayWire, TradeoffForecastResult } from "../engine/types";
import type { QForecastEntry } from "../charts/tradeoffForecast";
import { resolveStoreSpoilageSlot } from "./chartSlots";
import { ChapterTabs } from "./ChapterTabs";
import { ChartUnavailable } from "./ChartUnavailable";
import { DayInspector } from "./DayInspector";
import { SecondaryChrome } from "./SecondaryChrome";
import { EconomicsPane } from "./EconomicsPane";
import { EventsPane } from "./EventsPane";
import { GuidedPaths, type GuidedPath } from "./GuidedPaths";
import { InsightStrip } from "./InsightStrip";
import { OperatorBar } from "./OperatorBar";

/** Boot imperative studio (D3 + adapters). Requires StudioLayout mounted under #app. */
export function initStudio(app: HTMLElement): () => void {
  if (app.dataset.studioInit === "1") {
    return () => undefined;
  }
  app.dataset.studioInit = "1";
  if (!app.querySelector(".shell.studio")) {
    throw new Error("StudioLayout shell missing under #app");
  }

  const studioEnv = import.meta.env as ImportMetaEnv & StudioEnv;
  const adapterKind = resolveStudioAdapterKind(studioEnv);
  const footerEl = document.querySelector("#studio-footer");
  if (footerEl) {
    footerEl.textContent = studioFooterCopy(adapterKind);
    footerEl.setAttribute("data-engine-adapter", adapterKind);
    footerEl.setAttribute(
      "data-vite-engine-adapter",
      studioEnv.VITE_ENGINE_ADAPTER ?? "",
    );
  }
  const adapter = createStudioAdapter({
    env: studioEnv,
  });
  const engineStatus = createEngineStatusTracker("loading");
  const engineStatusEl = document.querySelector<HTMLElement>("#engine-status");
  if (engineStatusEl) {
    engineStatus.subscribe((kind) => {
      applyEngineStatusChip(engineStatusEl, kind, adapterKind);
    });
  }
  const projector = new ViewModelProjector();
  let vm: ViewModel = projector.getViewModel();
  let showTruth = loadShowTruth();
  /** Snapshot schedule for next-order step_n + weekday chrome (T-086). */
  let schedule: ScheduleWire | null = null;

  function formatAdapterError(err: unknown): string {
    if (err instanceof Error) return err.message;
    return String(err);
  }

  /** Snap order qty to case multiples using the projector's local config. */
  function snapOrder(qty: number): number {
    const cs = Math.max(1, Math.round(vm.config.case_size));
    if (qty <= 0) return 0;
    return Math.round(qty / cs) * cs;
  }

  function captureSchedule(snap: { schedule?: ScheduleWire }): void {
    schedule = snap.schedule
      ? {
          ...snap.schedule,
          delivery_weekdays: [...snap.schedule.delivery_weekdays],
          order_weekdays: [...snap.schedule.order_weekdays],
        }
      : null;
  }

  function controlsState() {
    return { ...controlsFromVm(vm, orderQty, schedule), catchingUp };
  }

  let orderQty = snapOrder(24);
  let catchingUp = false; // catch-up: pause Autopilot, then resume
  let hoveredDay: HoverDay = null;
  let hoveredPoint: HoverPoint = null;
  let activeSection: SectionId = loadSection();
  let controllerState: ControllerControlsState = {
    ...DEFAULT_CONTROLLER_CONTROLS,
  };
  let bootstrapped = false;
  let tradeoffForecasts: QForecastEntry[] = [];
  let eventDays: EventDayWire[] = [];
  let eventsLoading = false;
  let lastEventsKey = "";

  function controllerToActOpts(): ActOpts {
    const s = controllerState;
    const budgets: NonNullable<ActOpts["budgets"]> = {
      alpha: s.alpha,
      rho: s.rho,
      H: s.H,
      n_rollout_paths: s.n_rollout_paths,
      candidate_case_radius: s.candidate_case_radius,
      n_particles: s.n_particles,
    };
    if (s.policy === "constant") {
      budgets.order_qty = orderQty;
    }
    return { policy: s.policy, budgets };
  }

  let autopilot!: ReturnType<typeof createAutopilotLoop>;

  function syncAutopilotChrome(): void {
    renderSecondaryChrome();
  }

  const els = {
    linked: document.querySelector("#linked-charts") as HTMLElement,
    sales: document.querySelector("#chart-sales") as HTMLElement,
    stockout: document.querySelector("#chart-stockout") as HTMLElement,
    history: document.querySelector("#chart-history") as HTMLElement,
    spoil: document.querySelector("#chart-spoil") as HTMLElement,
    belief: document.querySelector("#chart-belief") as HTMLElement,
    beliefAgeMarginal: document.querySelector(
      "#chart-belief-age-marginal",
    ) as HTMLElement,
    beliefLg: document.querySelector("#chart-belief-lg") as HTMLElement,
    hoverNote: document.querySelector("#hover-note") as HTMLElement,
    sectionControls: document.querySelector("#section-controls") as HTMLElement,
    demand: document.querySelector("#chart-demand") as HTMLElement,
    salesDemand: document.querySelector("#chart-sales-demand") as HTMLElement,
    inventory: document.querySelector("#chart-inventory") as HTMLElement,
    ageComp: document.querySelector("#chart-age-comp") as HTMLElement,
    arrivalPrior: document.querySelector("#chart-arrival-prior") as HTMLElement,
    arrivalShift: document.querySelector("#chart-arrival-shift") as HTMLElement,
    arrheniusTemp: document.querySelector("#chart-arrhenius-temp") as HTMLElement,
    gammaPath: document.querySelector("#chart-gamma-path") as HTMLElement,
    controllerOrders: document.querySelector(
      "#chart-controller-orders",
    ) as HTMLElement,
    focusTitle: document.querySelector("#focus-title") as HTMLElement,
    focusBlurb: document.querySelector("#focus-blurb") as HTMLElement,
    focusPane: document.querySelector(".tuning-dock") as HTMLElement,
  };

  const economicsPaneHost = document.querySelector("#economics-pane-host");
  const eventsPaneHost = document.querySelector("#events-pane-host");
  const economicsPaneRoot = economicsPaneHost ? createRoot(economicsPaneHost) : null;
  const eventsPaneRoot = eventsPaneHost ? createRoot(eventsPaneHost) : null;

  const insightStripHost = document.querySelector("#insight-strip-host");
  const guidedPathsHost = document.querySelector("#guided-paths-host");
  const chapterTabsHost = document.querySelector("#chapter-tabs-host");
  const secondaryChromeHost = document.querySelector("#secondary-chrome-host");
  const operatorBarHost = document.querySelector("#operator-bar-host");
  const insightStripRoot = insightStripHost
    ? createRoot(insightStripHost)
    : null;
  const guidedPathsRoot = guidedPathsHost ? createRoot(guidedPathsHost) : null;
  const chapterTabsRoot = chapterTabsHost ? createRoot(chapterTabsHost) : null;
  const secondaryChromeRoot = secondaryChromeHost
    ? createRoot(secondaryChromeHost)
    : null;
  const operatorBarRoot = operatorBarHost ? createRoot(operatorBarHost) : null;

  async function fetchTradeoffForecast(): Promise<void> {
    if (typeof adapter.tradeoffForecast !== "function") return;
    try {
      const result = (await adapter.tradeoffForecast()) as TradeoffForecastResult;
      tradeoffForecasts = result.candidates ?? [];
    } catch {
      tradeoffForecasts = [];
    }
  }

  async function fetchEvents(): Promise<void> {
    if (typeof adapter.events !== "function" || !schedule) return;
    const sinceDay = previousOrderDayFromSchedule(vm.episode_day, schedule);
    const key = `${vm.episode_day}:${channelsCacheKey(vm.config.obs_channels)}:${sinceDay}`;
    if (key === lastEventsKey) return;
    lastEventsKey = key;
    eventsLoading = true;
    renderEventsPane();
    try {
      const result = await adapter.events({ since_day: sinceDay });
      eventDays = result.days ?? [];
    } catch {
      eventDays = [];
    } finally {
      eventsLoading = false;
      renderEventsPane();
    }
  }

  function renderEconomicsPane(): void {
    if (!economicsPaneRoot) return;
    economicsPaneRoot.render(createElement(EconomicsPane, { vm }));
  }

  function renderEventsPane(): void {
    if (!eventsPaneRoot) return;
    eventsPaneRoot.render(
      createElement(EventsPane, {
        vm: {
          episode_day: vm.episode_day,
          history: vm.history.map((d) => ({
            day: d.day,
            missed: d.stockout,
          })),
          config: vm.config,
        },
        showTruth,
        events: eventDays,
        loading: eventsLoading,
      }),
    );
  }
  let dayInspectorPortal = document.getElementById("day-inspector-portal");
  if (!dayInspectorPortal) {
    dayInspectorPortal = document.createElement("div");
    dayInspectorPortal.id = "day-inspector-portal";
    document.body.appendChild(dayInspectorPortal);
  }
  const dayInspectorRoot = createRoot(dayInspectorPortal);
  let spoilageUnavailableRoot: Root | null = null;

  function renderInsightStrip(): void {
    if (!insightStripRoot || !schedule) return;
    insightStripRoot.render(
      createElement(InsightStrip, { vm, schedule }),
    );
  }

  function renderDayInspector(): void {
    dayInspectorRoot.render(
      createElement(DayInspector, { day: hoveredDay, point: hoveredPoint, vm }),
    );
  }

  function hintAutoplay(): void {
    const toggleBtn = document.querySelector<HTMLButtonElement>(
      "#btn-autopilot-toggle",
    );
    if (!toggleBtn) return;
    toggleBtn.classList.add("autopilot-hint");
    window.setTimeout(() => toggleBtn.classList.remove("autopilot-hint"), 2400);
  }

  function onGuidedPathSelect(path: GuidedPath): void {
    void railHandlers.onSetObsPreset(path.scenario);
    setSection(path.section);
    if (path.autoplayHint) {
      hintAutoplay();
    }
  }

  function renderGuidedPaths(): void {
    if (!guidedPathsRoot) return;
    guidedPathsRoot.render(
      createElement(GuidedPaths, { onSelect: onGuidedPathSelect }),
    );
  }

  function renderChapterTabs(): void {
    if (!chapterTabsRoot) return;
    chapterTabsRoot.render(
      createElement(ChapterTabs, {
        activeSection,
        onSelectSection: setSection,
      }),
    );
  }

  function renderSecondaryChrome(): void {
    if (secondaryChromeRoot) {
      secondaryChromeRoot.render(
        createElement(SecondaryChrome, {
          vm,
          showTruth,
          catchingUp,
          orderQty,
          onSetObsChannels: (ch) => railHandlers.onSetObsChannels(ch),
          onSetObsPreset: (id) => railHandlers.onSetObsPreset(id),
          onShowTruthChange: (on) => railHandlers.onShowTruthChange(on),
          tradeoffForecasts,
        }),
      );
    }
    if (operatorBarRoot) {
      operatorBarRoot.render(
        createElement(OperatorBar, {
          vm,
          catchingUp,
          autopilotRunning: autopilot?.isRunning() ?? false,
          orderQty,
          onAdvance: () => railHandlers.onAdvance(),
          onReset: () => railHandlers.onReset(),
          onAutopilotPlay: () => railHandlers.onAutopilotPlay(),
          onAutopilotPause: () => railHandlers.onAutopilotPause(),
          onOrderChange: (qty) => {
            orderQty = snapOrder(qty);
            sectionControlsApi.update(controlsState());
            renderSecondaryChrome();
          },
        }),
      );
    }
  }

  const railHandlers = {
    onAdvance: () => {},
    onReset: () => {},
    onAutopilotPlay: () => {},
    onAutopilotPause: () => {},
    onSetObsChannels: (_ch: ObsChannels) => {},
    onSetObsPreset: (_id: ScenarioId) => {},
    onShowTruthChange: (_on: boolean) => {},
  };

  function applyHoverStyles(day: HoverDay): void {
    setMarginalHover(els.sales, day);
    setMarginalHover(els.stockout, day);
    setBeliefFreshnessTimeHover(els.history, day);
    setSalesDemandHover(els.salesDemand, day);
    setWasteBarsHover(els.spoil, day);
  }

  function onHoverDay(day: HoverDay, point: HoverPoint): void {
    const sameDay = hoveredDay === day;
    const samePoint =
      (point === null && hoveredPoint === null) ||
      (point !== null &&
        hoveredPoint !== null &&
        point.clientX === hoveredPoint.clientX &&
        point.clientY === hoveredPoint.clientY);
    if (sameDay && samePoint) return;
    hoveredDay = day;
    hoveredPoint = point;
    els.hoverNote.textContent =
      day == null
        ? "Hover a day to highlight it everywhere"
        : `Day ${day} highlighted`;
    applyHoverStyles(day);
    renderDayInspector();
  }

  attachLinkedHover(els.linked, () => vm.history.map((d) => d.day), {
    onDay: onHoverDay,
  });

  function historyForCharts(): ViewModel["history"] {
    if (showTruth) return vm.history;
    return vm.history.map((d) => ({
      ...d,
      lots: [],
      f_at_receipt: null,
    }));
  }

  function syncTruthCaptions(): void {
    document.querySelectorAll<HTMLElement>("[data-truth-caption]").forEach((el) => {
      const kind = el.dataset.truthCaption;
      if (kind === "belief" || kind === "belief-lg") {
        el.textContent = showTruth
          ? "Freshness histogram (truth overlay on)"
          : "Freshness histogram";
      }
      if (kind === "lots") {
        el.textContent =
          !showTruth && vm.history.length > 0
            ? "Freshness × time (turn on Sim truth overlay to see lot freshness)"
            : "Freshness × time";
      }
    });
    const observation = STUDIO_SECTIONS.find((s) => s.id === "observation");
    if (observation && activeSection === "observation") {
      els.focusBlurb.textContent = showTruth
        ? `${observation.blurb} Truth lots overlay when enabled.`
        : observation.blurb;
    }
  }

  function plotVisible(plotId: string): boolean {
    const node = document.querySelector(
      `.focus-plot[data-plot="${plotId}"]`,
    ) as HTMLElement | null;
    return !!node && !node.hidden;
  }

  function renderCockpitBelief(): void {
    const flat = vm.belief_history.at(-1)?.flatBelief;
    if (flat) {
      const data = freshnessHistogramDataFromFlat(flat, vm.live_lots);
      renderFreshnessHistogram(els.beliefLg, data, showTruth, 150);
    } else {
      els.beliefLg.replaceChildren();
    }
    els.beliefAgeMarginal.replaceChildren();
  }

  function renderRunStripCharts(): void {
    const invSeries = showTruth
      ? inventorySeries(vm.history, vm.config)
      : inventorySeriesFromBelief(vm.belief_history, vm.config);
    renderInventoryTarget(els.inventory, vm.history, vm.config, 76, invSeries);
    renderControllerOrders(els.controllerOrders, vm.history, 76);
    const ageRows = showTruth
      ? ageCompositionSeries(vm.history)
      : ageCompositionSeriesFromBelief(vm.belief_history);
    renderAgeComposition(
      els.ageComp,
      vm.history,
      76,
      ageRows,
      showTruth ? "age" : "freshness",
    );
  }

  function renderStore() {
    const yMax = marginalYMax(vm.history);
    renderMarginal(els.sales, vm.history, "sales", 48, yMax);
    renderMarginal(els.stockout, vm.history, "stockout", 48, yMax);
    renderBeliefFreshnessTime(
      els.history,
      vm.history,
      vm.belief_history,
      showTruth,
      { height: 220 },
    );
    renderSalesDemand(els.salesDemand, vm.history, 130);
    const spoilSlot = resolveStoreSpoilageSlot({
      scenario: vm.config.obs_scenario,
      showTruth,
    });
    if (spoilSlot.kind === "unavailable") {
      if (!spoilageUnavailableRoot) {
        spoilageUnavailableRoot = createRoot(els.spoil);
      }
      flushSync(() => {
        spoilageUnavailableRoot!.render(
          createElement(ChartUnavailable, {
            plotId: "store-spoilage",
            caption: "Daily waste is not observed at this knowledge rung.",
          }),
        );
      });
    } else {
      if (spoilageUnavailableRoot) {
        flushSync(() => {
          spoilageUnavailableRoot!.render(null);
        });
      }
      renderWasteBars(els.spoil, vm.history, 86, wasteBarYMax(vm.history));
    }
    renderCockpitBelief();
    applyHoverStyles(hoveredDay);
  }

  function renderActiveFocusPlots(): void {
    renderRunStripCharts();
    if (plotVisible("plot-inventory")) {
      const invSeries = showTruth
        ? inventorySeries(vm.history, vm.config)
        : inventorySeriesFromBelief(vm.belief_history, vm.config);
      renderInventoryTarget(els.inventory, vm.history, vm.config, 170, invSeries);
    }
    if (plotVisible("plot-age-comp")) {
      const ageRows = showTruth
        ? ageCompositionSeries(vm.history)
        : ageCompositionSeriesFromBelief(vm.belief_history);
      renderAgeComposition(
        els.ageComp,
        vm.history,
        140,
        ageRows,
        showTruth ? "age" : "freshness",
      );
    }
    // Demand DOW chart lives in #demand-chart-slot (T-130 colocation), not
    // .focus-plot[data-plot="plot-demand"] — gate on active section instead.
    if (activeSection === "demand" && schedule) {
      renderDemandDist(
        els.demand,
        vm.demand_summary,
        schedule,
        160,
      );
    }
    if (plotVisible("plot-arrival-prior")) {
      renderArrivalPrior(
        els.arrivalPrior,
        vm.config,
        historyForCharts(),
        160,
        arrivalRugAvailable(
          vm.config.obs_channels ?? channelsForPreset(vm.config.obs_scenario),
          showTruth,
        ),
      );
    }
    if (plotVisible("plot-arrival-shift")) {
      renderArrivalShift(els.arrivalShift, vm.config, 150);
    }
    if (plotVisible("plot-arrhenius-temp")) {
      renderArrheniusTemp(els.arrheniusTemp, vm.config, 160);
    }
    if (plotVisible("plot-gamma-path")) {
      renderGammaFreshnessPath(els.gammaPath, vm.config, 170);
    }
    if (plotVisible("plot-controller-orders")) {
      renderControllerOrders(els.controllerOrders, vm.history, 160);
    }
  }

  function syncTuningDockTabs(): void {
    document
      .querySelectorAll<HTMLButtonElement>(".tuning-dock-tabs [data-section]")
      .forEach((tab) => {
        const selected = tab.dataset.section === activeSection;
        tab.setAttribute("aria-selected", selected ? "true" : "false");
        tab.tabIndex = selected ? 0 : -1;
      });
  }

  function setSection(id: SectionId): void {
    activeSection = id;
    saveSection(id);
    const meta = STUDIO_SECTIONS.find((s) => s.id === id)!;

    renderChapterTabs();
    syncTuningDockTabs();

    els.focusTitle.textContent = meta.label;
    els.focusBlurb.textContent = meta.blurb;
    sectionControlsApi.showSection(id);

    document.querySelectorAll<HTMLElement>(".focus-plot").forEach((plot) => {
      const pid = plot.dataset.plot ?? "";
      plot.hidden = !meta.plotIds.includes(pid);
    });

    els.focusPane.classList.remove("focus-flash");
    void els.focusPane.offsetWidth;
    els.focusPane.classList.add("focus-flash");

    if (id === "demand") {
      const slot = document.querySelector("#demand-chart-slot");
      if (slot && els.demand.parentElement !== slot) {
        slot.appendChild(els.demand);
      }
    }

    renderActiveFocusPlots();
    syncTruthCaptions();

    // Defensive re-render one frame later: a plot's container can still
    // report a stale/near-zero clientWidth in the same tick that its
    // ancestor's `hidden` flips off (T-127 "demand chart looks weird" bug),
    // so re-measure once the browser has actually completed layout.
    if (typeof requestAnimationFrame === "function") {
      requestAnimationFrame(() => renderActiveFocusPlots());
    }
  }

  function renderAll(): void {
    syncTruthCaptions();
    renderStore();
    renderActiveFocusPlots();
    renderInsightStrip();
    renderGuidedPaths();
    renderChapterTabs();
    renderDayInspector();
    renderEconomicsPane();
    renderEventsPane();
    renderSecondaryChrome();
    orderQty = snapOrder(orderQty);
    const state = controlsState();
    sectionControlsApi.update(state);
    wireDemandPreview();
  }

  async function refreshRemotePanes(): Promise<void> {
    await Promise.all([fetchTradeoffForecast(), fetchEvents()]);
    renderSecondaryChrome();
    renderEconomicsPane();
  }

  function wireDemandPreview(): void {
    const slider = document.querySelector("#demand_mu") as HTMLInputElement | null;
    if (!slider || slider.dataset.previewBound === "1") return;
    slider.dataset.previewBound = "1";
    bindDemandSliderPreview({
      chartHost: els.demand,
      slider,
      projector,
      schedule,
    });
  }

  async function advanceEpisode(): Promise<void> {
    try {
      if (vm.episode_day >= EPISODE_HORIZON) {
        return;
      }
      if (!schedule) {
        throw new Error("schedule missing — init/reset before advance");
      }
      const orders = buildStepNOrders(vm.episode_day, orderQty, schedule);
      const deltas = await adapter.step_n(orders);
      for (const delta of deltas) {
        vm = projector.applyDelta(delta);
      }
      if (deltas.length > 0) {
        const completed = deltas[deltas.length - 1]!.episode_day;
        vm = { ...vm, episode_day: completed + 1 };
      }
      onHoverDay(null, null);
      renderAll();
      void refreshRemotePanes();
    } catch (err) {
      reportStudioAdapterError(
        `Advance failed: ${formatAdapterError(err)}`,
        undefined,
        err,
      );
    }
  }

  async function resetEpisode(): Promise<void> {
    try {
      if (autopilot.isRunning()) {
        autopilot.pause();
        syncAutopilotChrome();
      }
      const snap = await adapter.reset({ ...vm.config });
      captureSchedule(snap);
      vm = projector.applySnapshot(snap);
      projector.markConfigApplied();
      orderQty = snapOrder(orderQty);
      onHoverDay(null, null);
      renderAll();
      void refreshRemotePanes();
    } catch (err) {
      reportStudioAdapterError(
        `Reset failed: ${formatAdapterError(err)}`,
        undefined,
        err,
      );
    }
  }

  autopilot = createAutopilotLoop({
    act: (opts) => {
      if (vm.episode_day >= EPISODE_HORIZON) {
        autopilot.pause();
        return Promise.reject(
          new Error("episode finished at day 90; Reset to start another"),
        );
      }
      if (typeof adapter.act !== "function") {
        return Promise.reject(new Error("adapter.act unavailable"));
      }
      return adapter.act(opts);
    },
    applyDelta(delta) {
      // Sync order slider before renderAll so chrome matches day.order_qty (T-100 AC).
      const q = (delta.day as { order_qty?: number } | undefined)?.order_qty;
      if (typeof q === "number") {
        orderQty = snapOrder(q);
      }
      vm = projector.applyDelta(delta);
      // DayDelta.episode_day is the completed day; next act cursor is +1.
      vm = { ...vm, episode_day: delta.episode_day + 1 };
      if (vm.episode_day >= EPISODE_HORIZON) {
        autopilot.pause();
      }
      onHoverDay(null, null);
      renderAll();
      void refreshRemotePanes();
    },
    getOpts: controllerToActOpts,
    getIntervalMs: () => controllerState.intervalMs,
    isConfigDirty: () => vm.config_dirty,
    onError(err) {
      reportStudioAdapterError(
        `Autopilot failed: ${formatAdapterError(err)}`,
        undefined,
        err,
      );
      syncAutopilotChrome();
    },
    onTick(delta) {
      const q = (delta.day as { order_qty?: number } | undefined)?.order_qty;
      if (typeof q === "number") {
        orderQty = snapOrder(q);
        sectionControlsApi?.update(controlsFromVm(vm, orderQty, schedule));
        renderSecondaryChrome();
      }
      // Loop may pause for config_dirty after this callback returns.
      queueMicrotask(syncAutopilotChrome);
    },
  });

  let sectionControlsApi!: ReturnType<typeof mountSectionControls>;

  sectionControlsApi = mountSectionControls(
    els.sectionControls,
    controlsState(),
    {
      onEconomicsChange(partial: Partial<Economics>) {
        // Local reproject only — never round-trip to the engine.
        vm = projector.setEconomics(partial);
        renderEconomicsPane();
        sectionControlsApi.update(controlsState());
      },
      onConfigChange(partial: Partial<SimConfig>) {
        // Stage knobs locally; engine applies on next reset/init (no Mock setConfig).
        vm = projector.setConfig(partial);
        if (partial.case_size != null) {
          orderQty = snapOrder(orderQty);
        }
        sectionControlsApi.update(controlsState());
        renderSecondaryChrome();
        renderActiveFocusPlots();
        // Autopilot pauses when staged config is dirty (AC).
        if (vm.config_dirty && autopilot.isRunning()) {
          autopilot.pause();
          syncAutopilotChrome();
        }
      },
      onSetObsScenario: (id) => {
        void railHandlers.onSetObsPreset(id);
      },
      onControllerChange(partial: Partial<ControllerControlsState>) {
        controllerState = { ...controllerState, ...partial };
        sectionControlsApi.updateController(controllerState);
      },
    },
    (caseSize) => {
      orderQty = snapOrder(orderQty);
      sectionControlsApi.update({
        ...controlsState(),
        orderQty,
        config: { ...vm.config, case_size: caseSize },
      });
      renderSecondaryChrome();
    },
    controllerState,
  );

  railHandlers.onAdvance = () => {
    void advanceEpisode();
  };
  railHandlers.onReset = () => {
    void resetEpisode();
  };
  railHandlers.onAutopilotPlay = () => {
    if (vm.episode_day >= EPISODE_HORIZON) {
      autopilot.pause();
      syncAutopilotChrome();
      return;
    }
    autopilot.play();
    syncAutopilotChrome();
  };
  railHandlers.onAutopilotPause = () => {
    autopilot.pause();
    syncAutopilotChrome();
  };
  async function applyObsSelection(
    channels: ObsChannels,
    obs_scenario: ScenarioId,
  ): Promise<void> {
    const setCh =
      adapter.set_obs_channels?.bind(adapter) ??
      adapter.setObsChannels?.bind(adapter);
    if (typeof setCh !== "function") {
      vm = projector.setConfig({ obs_channels: channels, obs_scenario });
      sectionControlsApi.update(controlsState());
      lastEventsKey = "";
      renderAll();
      void refreshRemotePanes();
      return;
    }
    const resumeAfter = autopilot.isRunning();
    if (resumeAfter) {
      autopilot.pause();
      syncAutopilotChrome();
    }
    catchingUp = true;
    sectionControlsApi.update(controlsState());
    renderSecondaryChrome();
    try {
      const snap = (await engineStatus.follow(setCh(channels))) as Snapshot;
      vm = projector.patchEngineState(snap);
      projector.setConfig({ obs_channels: channels, obs_scenario });
      lastEventsKey = "";
      renderAll();
      void refreshRemotePanes();
    } catch (err) {
      reportStudioAdapterError(
        `set_obs_channels failed: ${formatAdapterError(err)}`,
        undefined,
        err,
      );
    } finally {
      catchingUp = false;
      sectionControlsApi.update(controlsState());
      renderSecondaryChrome();
      if (resumeAfter) {
        autopilot.play();
        syncAutopilotChrome();
      }
    }
  }

  railHandlers.onSetObsPreset = async (id: ScenarioId) => {
    await applyObsSelection(channelsForPreset(id), id);
  };

  railHandlers.onSetObsChannels = async (channels: ObsChannels) => {
    let preset: ScenarioId = vm.config.obs_scenario;
    for (const id of ["P0", "P1", "F1", "F1s", "F2a", "F2", "F3"] as ScenarioId[]) {
      const presetCh = channelsForPreset(id);
      if (
        presetCh.code_type === channels.code_type &&
        presetCh.scan_waste === channels.scan_waste &&
        presetCh.delivery_history === channels.delivery_history
      ) {
        preset = id;
        break;
      }
    }
    await applyObsSelection(channels, preset);
  };
  railHandlers.onShowTruthChange = (show) => {
    showTruth = show;
    saveShowTruth(show);
    app.classList.toggle("studio--show-truth", show);
    renderAll();
  };

  window.addEventListener("keydown", (event) => {
    const tag = (event.target as HTMLElement | null)?.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA") return;

    const idx = STUDIO_SECTIONS.findIndex((s) => s.id === activeSection);
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      event.preventDefault();
      setSection(STUDIO_SECTIONS[(idx + 1) % STUDIO_SECTIONS.length]!.id);
      return;
    }
    if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      event.preventDefault();
      setSection(
        STUDIO_SECTIONS[(idx - 1 + STUDIO_SECTIONS.length) % STUDIO_SECTIONS.length]!
          .id,
      );
      return;
    }
    const n = Number(event.key);
    if (n >= 1 && n <= STUDIO_SECTIONS.length) {
      event.preventDefault();
      setSection(STUDIO_SECTIONS[n - 1]!.id);
    }
  });

  function wireTuningDockTabs(): void {
    document
      .querySelectorAll<HTMLButtonElement>(".tuning-dock-tabs [data-section]")
      .forEach((tab) => {
        if (tab.dataset.bound === "1") return;
        tab.dataset.bound = "1";
        tab.addEventListener("click", () => {
          const id = tab.dataset.section as SectionId | undefined;
          if (id) setSection(id);
        });
      });
  }

  wireTuningDockTabs();

  async function bootstrap(): Promise<void> {
    if (bootstrapped) return;
    bootstrapped = true;
    try {
      const snap = await engineStatus.follow(adapter.init({ ...vm.config }));
      captureSchedule(snap);
      vm = projector.applySnapshot(snap);
      projector.markConfigApplied();
      setSection(activeSection);
      renderAll();
      void refreshRemotePanes();
    } catch (err) {
      reportStudioAdapterError(
        `Init failed: ${formatAdapterError(err)}`,
        undefined,
        err,
      );
    }
  }

  void bootstrap();

  const onResize = () => {
    renderStore();
    renderActiveFocusPlots();
  };
  window.addEventListener("resize", onResize);
  return () => {
    window.removeEventListener("resize", onResize);
  };
}
