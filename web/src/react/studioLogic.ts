/** Studio runtime (T-121) — logic migrated from main.ts; shell in StudioLayout.tsx. */
import { createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { flushSync } from "react-dom";
import { bindDemandSliderPreview } from "../engine/demandPreview";
import { arrivalRugAvailable } from "../scenarioAvailability";
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
import { renderHistory, setHistoryHover } from "../charts/history";
import {
  marginalYMax,
  renderMarginal,
  setMarginalHover,
} from "../charts/marginals";
import { renderPnLTimeseries, setPnLHover } from "../charts/pnlTimeseries";
import { renderPnLTotals } from "../charts/pnlTotals";
import { renderBeliefAgeCount } from "../charts/beliefAgeCount";
import { renderBeliefAgeMarginal } from "../charts/beliefAgeMarginal";
import { renderSurvival } from "../charts/survival";
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
import { renderSalesDemand } from "../charts/salesDemand";
import {
  renderArrivalPrior,
  renderArrivalShift,
} from "../charts/arrivalPrior";
import {
  controlsFromVm,
  DEFAULT_CONTROLLER_CONTROLS,
  EPISODE_HORIZON,
  mountPlayChrome,
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
import type { Economics, HoverDay, ScenarioId, SimConfig, ViewModel } from "../types";
import type { ActOpts, ScheduleWire, Snapshot } from "../engine/types";
import { buildStepNOrders } from "../calendar/nextOrderAdvance";
import { loadShowTruth, saveShowTruth, truthLots } from "../showTruth";
import { resolveStoreSpoilageSlot } from "./chartSlots";
import { ChapterTabs } from "./ChapterTabs";
import { ChartUnavailable } from "./ChartUnavailable";
import { DayInspector } from "./DayInspector";
import { DecisionRail } from "./DecisionRail";
import { InsightStrip } from "./InsightStrip";

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
    baseUrl: studioEnv.VITE_ENGINE_API_BASE_URL ?? studioEnv.VITE_API_BASE_URL,
    // Never pass the Pyodide worker URL into wasm (that boots micropip + GitHub wheel).
    workerUrl:
      adapterKind === "wasm"
        ? studioEnv.VITE_WASM_WORKER_URL
        : studioEnv.VITE_PYODIDE_WORKER_URL,
    wheelUrl: studioEnv.VITE_PYODIDE_WHEEL_URL,
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

  let playChromeApi!: ReturnType<typeof mountPlayChrome>;
  let autopilot!: ReturnType<typeof createAutopilotLoop>;

  function syncAutopilotChrome(): void {
    playChromeApi.setAutopilotRunning(autopilot.isRunning());
    renderDecisionRailChrome();
  }

  const els = {
    linked: document.querySelector("#linked-charts") as HTMLElement,
    sales: document.querySelector("#chart-sales") as HTMLElement,
    stockout: document.querySelector("#chart-stockout") as HTMLElement,
    history: document.querySelector("#chart-history") as HTMLElement,
    spoil: document.querySelector("#chart-spoil") as HTMLElement,
    pnlSeries: document.querySelector("#chart-pnl-series") as HTMLElement,
    pnlSpark: document.querySelector("#chart-pnl-spark") as HTMLElement,
    pnlTotals: document.querySelector("#chart-pnl-totals") as HTMLElement,
    belief: document.querySelector("#chart-belief") as HTMLElement,
    beliefAgeMarginal: document.querySelector(
      "#chart-belief-age-marginal",
    ) as HTMLElement,
    beliefLg: document.querySelector("#chart-belief-lg") as HTMLElement,
    hoverNote: document.querySelector("#hover-note") as HTMLElement,
    playChrome: document.querySelector("#play-chrome") as HTMLElement,
    sectionControls: document.querySelector("#section-controls") as HTMLElement,
    survival: document.querySelector("#chart-survival") as HTMLElement,
    demand: document.querySelector("#chart-demand") as HTMLElement,
    salesDemand: document.querySelector("#chart-sales-demand") as HTMLElement,
    inventory: document.querySelector("#chart-inventory") as HTMLElement,
    ageComp: document.querySelector("#chart-age-comp") as HTMLElement,
    arrivalPrior: document.querySelector("#chart-arrival-prior") as HTMLElement,
    arrivalShift: document.querySelector("#chart-arrival-shift") as HTMLElement,
    controllerOrders: document.querySelector(
      "#chart-controller-orders",
    ) as HTMLElement,
    focusTitle: document.querySelector("#focus-title") as HTMLElement,
    focusBlurb: document.querySelector("#focus-blurb") as HTMLElement,
    focusPane: document.querySelector("#focus-pane") as HTMLElement,
  };

  const insightStripHost = document.querySelector("#insight-strip-host");
  const chapterTabsHost = document.querySelector("#chapter-tabs-host");
  const decisionRailHost = document.querySelector("#decision-rail-host");
  const insightStripRoot = insightStripHost
    ? createRoot(insightStripHost)
    : null;
  const chapterTabsRoot = chapterTabsHost ? createRoot(chapterTabsHost) : null;
  const decisionRailRoot = decisionRailHost ? createRoot(decisionRailHost) : null;
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

  function renderChapterTabs(): void {
    if (!chapterTabsRoot) return;
    chapterTabsRoot.render(
      createElement(ChapterTabs, {
        activeSection,
        onSelectSection: setSection,
      }),
    );
  }

  function renderDecisionRailChrome(): void {
    if (!decisionRailRoot) return;
    decisionRailRoot.render(
      createElement(DecisionRail, {
        vm,
        showTruth,
        catchingUp,
        autopilotRunning: autopilot?.isRunning() ?? false,
        orderQty,
        activeSection,
        onAdvance: () => railHandlers.onAdvance(),
        onReset: () => railHandlers.onReset(),
        onAutopilotPlay: () => railHandlers.onAutopilotPlay(),
        onAutopilotPause: () => railHandlers.onAutopilotPause(),
        onSetObsScenario: (id) => railHandlers.onSetObsScenario(id),
        onShowTruthChange: (on) => railHandlers.onShowTruthChange(on),
        onOrderChange: (qty) => {
          orderQty = snapOrder(qty);
        },
      }),
    );
  }

  const railHandlers = {
    onAdvance: () => {},
    onReset: () => {},
    onAutopilotPlay: () => {},
    onAutopilotPause: () => {},
    onSetObsScenario: (_id: ScenarioId) => {},
    onShowTruthChange: (_on: boolean) => {},
  };

  function applyHoverStyles(day: HoverDay): void {
    setMarginalHover(els.sales, day);
    setMarginalHover(els.stockout, day);
    setHistoryHover(els.history, day);
    setMarginalHover(els.spoil, day);
    if (!els.pnlSeries.closest(".focus-plot")?.hasAttribute("hidden")) {
      setPnLHover(els.pnlSeries, day);
    }
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
      age_at_receipt: null,
    }));
  }

  function syncTruthCaptions(): void {
    document.querySelectorAll<HTMLElement>("[data-truth-caption]").forEach((el) => {
      const kind = el.dataset.truthCaption;
      if (kind === "belief" || kind === "belief-lg") {
        el.textContent = showTruth ? "Belief vs truth" : "Belief";
      }
      if (kind === "lots") {
        el.textContent =
          !showTruth && vm.history.length > 0
            ? "Lots · day × age (turn on Sim truth overlay to see lot ages)"
            : "Lots · day × age";
      }
    });
    const belief = STUDIO_SECTIONS.find((s) => s.id === "belief");
    if (belief && activeSection === "belief") {
      els.focusBlurb.textContent = showTruth
        ? `${belief.blurb} Truth lots overlay when enabled.`
        : belief.blurb;
    }
  }

  function plotVisible(plotId: string): boolean {
    const node = document.querySelector(
      `.focus-plot[data-plot="${plotId}"]`,
    ) as HTMLElement | null;
    return !!node && !node.hidden;
  }

  function renderStore() {
    const yMax = marginalYMax(vm.history);
    renderMarginal(els.sales, vm.history, "sales", 72, yMax);
    renderMarginal(els.stockout, vm.history, "stockout", 72, yMax);
    renderHistory(els.history, historyForCharts(), { height: 220 });
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
      spoilageUnavailableRoot?.render(null);
      renderMarginal(els.spoil, vm.history, "spoilage", 86);
    }
    applyHoverStyles(hoveredDay);
  }

  function renderChrome(): void {
    renderPnLTotals(els.pnlTotals, vm);
    renderPnLTimeseries(els.pnlSpark, vm.pnl_series, 118);
  }

  function renderActiveFocusPlots(): void {
    if (plotVisible("plot-belief-age-marginal")) {
      renderBeliefAgeMarginal(els.beliefAgeMarginal, vm.belief, 72);
    }
    if (plotVisible("plot-belief-lg")) {
      renderBeliefAgeCount(
        els.beliefLg,
        vm.belief,
        truthLots(showTruth, vm.live_lots),
        280,
      );
    }
    if (plotVisible("plot-sales-demand")) {
      renderSalesDemand(els.salesDemand, vm.history, 130);
    }
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
      renderAgeComposition(els.ageComp, vm.history, 140, ageRows);
    }
    if (plotVisible("plot-pnl")) {
      renderPnLTimeseries(els.pnlSeries, vm.pnl_series, 160);
      applyHoverStyles(hoveredDay);
    }
    if (plotVisible("plot-survival")) {
      renderSurvival(
        els.survival,
        vm.config,
        truthLots(showTruth, vm.live_lots),
        160,
      );
    }
    if (plotVisible("plot-demand")) {
      renderDemandDist(
        els.demand,
        vm.demand_summary,
        vm.schedule,
        160,
      );
    }
    if (plotVisible("plot-arrival-prior")) {
      renderArrivalPrior(
        els.arrivalPrior,
        vm.config,
        historyForCharts(),
        160,
        arrivalRugAvailable(vm.config.obs_scenario, showTruth),
      );
    }
    if (plotVisible("plot-arrival-shift")) {
      renderArrivalShift(els.arrivalShift, vm.config, 150);
    }
    if (plotVisible("plot-controller-orders")) {
      renderControllerOrders(els.controllerOrders, vm.history, 160);
    }
  }

  function setSection(id: SectionId): void {
    activeSection = id;
    saveSection(id);
    const meta = STUDIO_SECTIONS.find((s) => s.id === id)!;

    renderChapterTabs();

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

    renderActiveFocusPlots();
    syncTruthCaptions();
  }

  function renderAll(): void {
    syncTruthCaptions();
    renderStore();
    renderChrome();
    renderActiveFocusPlots();
    renderInsightStrip();
    renderChapterTabs();
    renderDayInspector();
    renderDecisionRailChrome();
    orderQty = snapOrder(orderQty);
    const state = controlsState();
    playChromeApi.update(state);
    sectionControlsApi.update(state);
    wireDemandPreview();
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

  playChromeApi = mountPlayChrome(
    els.playChrome,
    controlsState(),
    {
      onOrderChange(qty) {
        orderQty = qty;
      },
      onAdvance() {
        void (async () => {
          try {
            if (vm.episode_day >= EPISODE_HORIZON) {
              return;
            }
            if (!schedule) {
              throw new Error("schedule missing — init/reset before advance");
            }
            const orders = buildStepNOrders(
              vm.episode_day,
              orderQty,
              schedule,
            );
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
          } catch (err) {
            reportStudioAdapterError(
              `Advance failed: ${formatAdapterError(err)}`,
              undefined,
              err,
            );
          }
        })();
      },
      onReset() {
        void (async () => {
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
          } catch (err) {
            reportStudioAdapterError(
              `Reset failed: ${formatAdapterError(err)}`,
              undefined,
              err,
            );
          }
        })();
      },
      onAutopilotPlay() {
        railHandlers.onAutopilotPlay();
      },
      onAutopilotPause() {
        railHandlers.onAutopilotPause();
      },
      onShowTruthChange(show) {
        showTruth = show;
        saveShowTruth(show);
        renderAll();
      },
    },
    {
      showTruth,
      truthClassTarget: app,
    },
  );

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
        playChromeApi.update(controlsFromVm(vm, orderQty));
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
        renderChrome();
        if (plotVisible("plot-pnl")) {
          renderPnLTimeseries(els.pnlSeries, vm.pnl_series, 160);
          applyHoverStyles(hoveredDay);
        }
        sectionControlsApi.update(controlsState());
      },
      onConfigChange(partial: Partial<SimConfig>) {
        // Stage knobs locally; engine applies on next reset/init (no Mock setConfig).
        vm = projector.setConfig(partial);
        if (partial.case_size != null) {
          orderQty = snapOrder(orderQty);
          playChromeApi.update(controlsState());
        }
        playChromeApi.update(controlsState());
        sectionControlsApi.update(controlsState());
        renderActiveFocusPlots();
        // Autopilot pauses when staged config is dirty (AC).
        if (vm.config_dirty && autopilot.isRunning()) {
          autopilot.pause();
          syncAutopilotChrome();
        }
      },
      onSetObsScenario: (id) => {
        void railHandlers.onSetObsScenario(id);
      },
      onControllerChange(partial: Partial<ControllerControlsState>) {
        controllerState = { ...controllerState, ...partial };
        sectionControlsApi.updateController(controllerState);
      },
    },
    (caseSize) => {
      orderQty = snapOrder(orderQty);
      playChromeApi.setOrderFromCaseChange(orderQty, caseSize);
    },
    controllerState,
  );

  railHandlers.onAdvance = () => {
    els.playChrome.querySelector<HTMLButtonElement>("#btn-advance")?.click();
  };
  railHandlers.onReset = () => {
    els.playChrome.querySelector<HTMLButtonElement>("#btn-reset")?.click();
  };
  railHandlers.onAutopilotPlay = () => {
    els.playChrome.querySelector<HTMLButtonElement>("#btn-autopilot-play")?.click();
  };
  railHandlers.onAutopilotPause = () => {
    els.playChrome.querySelector<HTMLButtonElement>("#btn-autopilot-pause")?.click();
  };
  railHandlers.onSetObsScenario = async (id: ScenarioId) => {
    const setObs =
      adapter.setObsScenario?.bind(adapter) ??
      adapter.set_obs_scenario?.bind(adapter);
    if (typeof setObs !== "function") {
      vm = projector.setConfig({ obs_scenario: id });
      sectionControlsApi.update(controlsState());
      renderAll();
      return;
    }
    const resumeAfter = autopilot.isRunning();
    if (resumeAfter) {
      autopilot.pause();
      syncAutopilotChrome();
    }
    catchingUp = true;
    sectionControlsApi.update(controlsState());
    renderDecisionRailChrome();
    try {
      const snap = (await engineStatus.follow(setObs(id))) as Snapshot;
      vm = projector.patchEngineState(snap);
      projector.setConfig({ obs_scenario: id });
      renderAll();
    } catch (err) {
      reportStudioAdapterError(
        `set_obs_scenario failed: ${formatAdapterError(err)}`,
        undefined,
        err,
      );
    } finally {
      catchingUp = false;
      sectionControlsApi.update(controlsState());
      renderDecisionRailChrome();
      if (resumeAfter) {
        autopilot.play();
        syncAutopilotChrome();
      }
    }
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
    renderChrome();
    renderActiveFocusPlots();
  };
  window.addEventListener("resize", onResize);
  return () => {
    window.removeEventListener("resize", onResize);
  };
}
