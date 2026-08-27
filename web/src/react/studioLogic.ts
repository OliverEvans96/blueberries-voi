/** Studio runtime (T-121) — logic migrated from main.ts; shell in StudioLayout.tsx. */
import { createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { flushSync } from "react-dom";
import { bindDemandSliderPreview } from "../engine/demandPreview";
import { arrivalRugAvailable } from "../scenarioAvailability";
import {
  applyMask,
  channelsCacheKey,
  channelsForPreset,
  maskFor,
  maskFromChannels,
  resolveDisplayObsScenario,
  type RichObsWire,
} from "../obsMask";
import { ViewModelProjector } from "../engine/projector";
import {
  applyEngineStatusChip,
  createEngineStatusTracker,
} from "../engine/engineStatus";
import {
  createStudioAdapter,
  reportStudioAdapterError,
  resolveStudioAdapterKind,
  STUDIO_PACKAGE_VERSION,
  studioFooterCopy,
  type StudioEnv,
} from "../engine/studioAdapter";
import {
  renderBeliefFreshnessTime,
  setBeliefFreshnessTimeHover,
  type BeliefFreshnessHoverFocus,
} from "../charts/beliefFreshnessTime";
import {
  BELIEF_FRESHNESS_TIME_HEIGHT,
  BELIEF_HISTOGRAM_HEIGHT,
  METRICS_STRIP_HEIGHT,
} from "../charts/chartHeights";
import {
  BELIEF_MAE_TOOLTIP,
  currentDistributionAbsError,
  currentMeanFAbsError,
  formatMeanFAbsError,
  meanDistributionAbsErrorOverHistory,
  meanMeanFAbsErrorOverHistory,
} from "../charts/beliefAccuracy";
import {
  emptyFreshnessHistogramData,
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
import {
  buildDemandForecastRows,
  salesDemandForecastAnchor,
  renderDailyDemand,
  renderDemandForecast,
  renderPickingVariability,
  setDemandForecastHover,
  setDemandHover,
} from "../charts/demandDist";
import {
  fCompositionSeries,
  fCompositionSeriesFromBelief,
  effectiveInventoryFromFlatBelief,
  inventorySeries,
  inventorySeriesFromBelief,
  renderFreshnessComposition,
  setFreshnessCompositionHover,
} from "../charts/inventoryTarget";
import {
  renderControllerOrders,
  setControllerOrdersHover,
} from "../charts/controllerOrders";
import { renderDampedSwDemo } from "../charts/dampedSwDemo";
import { renderPnLTimeseries, setPnLHover } from "../charts/pnlTimeseries";
import { renderPnLTotals } from "../charts/pnlTotals";
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
import {
  attachLinkedHover,
  type HoverChartSource,
  type HoverPoint,
} from "../hoverLink";
import {
  STUDIO_SECTIONS,
  loadSection,
  saveSection,
  type SectionId,
} from "../sections";
import type { Economics, HoverDay, ObsChannels, ScenarioId, SimConfig, ViewModel } from "../types";
import type { ActOpts, ScheduleWire, Snapshot } from "../engine/types";
import { buildStepNOrders } from "../calendar/nextOrderAdvance";
import {
  renderWeekCalendar,
  scheduleFromConfig,
  toggleDeliveryDay,
} from "../calendar/weekCalendar";
import { loadShowTruth, saveShowTruth } from "../showTruth";
import type { EventDayWire } from "../engine/types";
import { DayInspector } from "./DayInspector";
import { EventsPane } from "./EventsPane";
import { ObsControlsPane } from "./ObsControlsPane";
import { OperatorBar } from "./OperatorBar";
import { StudioLoadingDialog } from "./StudioLoadingDialog";
import { createDelayedLoadingHandle } from "../delayedLoading";
import { ReferenceDrawer, type ReferenceDrawerProps } from "./ReferenceDrawer";
import { TuningDrawer, type TuningDrawerProps } from "./TuningDrawer";
import { resolveStoreSpoilageSlot } from "./chartSlots";
import { ChartUnavailable } from "./ChartUnavailable";
import {
  clearRenderProfile,
  getRenderProfileReport,
  profileAsync,
  profileSync,
  setRenderProfiling,
  type RenderProfileRow,
} from "./renderProfile";
import {
  buildAdvanceSample,
  clearAdvanceProfile,
  getAdvancePipelineReport,
  isAdvanceProfiling,
  recordAdvanceSample,
  setAdvanceProfiling,
  type AdvancePipelineReport,
} from "./advanceProfile";
import { clearRpcProfile, setRpcProfiling } from "../engine/rpcProfile";

export {
  clearAdvanceProfile,
  clearRenderProfile,
  clearRpcProfile,
  getAdvancePipelineReport,
  getRenderProfileReport,
  setAdvanceProfiling,
  setRenderProfiling,
  setRpcProfiling,
  type AdvancePipelineReport,
  type RenderProfileRow,
};

/** Set by initStudio — profile one full Advance (await remote panes). */
let studioAdvanceOnce: (() => Promise<void>) | null = null;

/** Run N advance steps with profiling enabled; returns aggregated report. */
export async function studioProfileAdvanceSteps(
  steps: number,
): Promise<AdvancePipelineReport> {
  if (!studioAdvanceOnce) {
    throw new Error("studio not initialized — mount StudioLayout and call initStudio first");
  }
  setAdvanceProfiling(true);
  setRenderProfiling(true);
  setRpcProfiling(true);
  clearAdvanceProfile();
  clearRenderProfile();
  clearRpcProfile();
  for (let i = 0; i < steps; i++) {
    clearRenderProfile();
    await studioAdvanceOnce();
  }
  return getAdvancePipelineReport();
}

declare global {
  interface Window {
    __studioProfileAdvance?: (steps?: number) => Promise<AdvancePipelineReport>;
  }
}

/** Boot imperative studio (D3 + adapters). Requires StudioLayout mounted under mount root. */
export function initStudio(app: HTMLElement): () => void {
  if (app.dataset.studioInit === "1") {
    return () => undefined;
  }
  app.dataset.studioInit = "1";
  if (!app.querySelector(".shell.studio")) {
    throw new Error("StudioLayout shell missing under studio mount root");
  }

  const q = <T extends Element>(selector: string): T | null =>
    app.querySelector(selector) as T | null;
  const qa = <T extends Element>(selector: string): NodeListOf<T> =>
    app.querySelectorAll(selector);

  const studioEnv = import.meta.env as ImportMetaEnv & StudioEnv;
  const adapterKind = resolveStudioAdapterKind(studioEnv);
  const studioErrorEl = q<HTMLElement>("#studio-error");
  const footerEl = q<HTMLElement>("#studio-footer");
  if (footerEl) {
    footerEl.textContent = studioFooterCopy(adapterKind);
    footerEl.setAttribute("data-engine-adapter", adapterKind);
    footerEl.setAttribute("data-studio-version", STUDIO_PACKAGE_VERSION);
    footerEl.setAttribute(
      "data-vite-engine-adapter",
      studioEnv.VITE_ENGINE_ADAPTER ?? "",
    );
  }
  const adapter = createStudioAdapter({
    env: studioEnv,
  });
  let loadingMessage = "";
  let loadingDialogVisible = false;
  const engineStatus = createEngineStatusTracker("loading");
  const engineStatusEl = q<HTMLElement>("#engine-status");
  if (engineStatusEl) {
    engineStatus.subscribe((kind) => {
      applyEngineStatusChip(engineStatusEl, kind, adapterKind);
      const shell = q<HTMLElement>(".shell.studio");
      if (shell) {
        if (kind === "loading") {
          shell.setAttribute("aria-busy", "true");
        } else if (!loadingDialogVisible) {
          shell.removeAttribute("aria-busy");
        }
      }
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
    const previewSchedule =
      vm.config.delivery_weekdays?.length > 0
        ? scheduleFromConfig(vm.config)
        : schedule;
    return {
      ...controlsFromVm(vm, orderQty, previewSchedule),
      catchingUp,
    };
  }

  let orderQty = snapOrder(24);
  let catchingUp = false; // catch-up: pause Autopilot, then resume
  let advancing = false; // manual Advance in flight (T-149)
  let hoveredDay: HoverDay = null;
  let hoveredPoint: HoverPoint = null;
  let hoveredChartSource: HoverChartSource = null;
  let activeSection: SectionId = loadSection();
  let controllerState: ControllerControlsState = {
    ...DEFAULT_CONTROLLER_CONTROLS,
  };
  let bootstrapped = false;
  let eventDays: EventDayWire[] = [];
  let eventsLoading = false;
  let eventsRefreshing = false;
  let lastEventsKey = "";
  let frameGen = 0;

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
    renderOperatorBar();
    renderObsControlsPane();
  }

  const els = {
    get linked(): HTMLElement {
      return q<HTMLElement>("#linked-charts")!;
    },
    get sales(): HTMLElement {
      return q<HTMLElement>("#chart-sales")!;
    },
    get stockout(): HTMLElement {
      return q<HTMLElement>("#chart-stockout")!;
    },
    get history(): HTMLElement {
      return q<HTMLElement>("#chart-history")!;
    },
    get belief(): HTMLElement {
      return q<HTMLElement>("#chart-belief")!;
    },
    get beliefAgeMarginal(): HTMLElement {
      return q<HTMLElement>("#chart-belief-age-marginal")!;
    },
    get beliefLg(): HTMLElement {
      return q<HTMLElement>("#chart-belief-lg")!;
    },
    get hoverNote(): HTMLElement {
      return q<HTMLElement>("#hover-note")!;
    },
    get sectionControls(): HTMLElement {
      return q<HTMLElement>("#section-controls")!;
    },
    get demand(): HTMLElement {
      return q<HTMLElement>("#chart-demand")!;
    },
    get demandForecast(): HTMLElement {
      return q<HTMLElement>("#chart-demand-forecast-host")!;
    },
    get salesDemand(): HTMLElement {
      return q<HTMLElement>("#chart-sales-demand")!;
    },
    get ageComp(): HTMLElement {
      return q<HTMLElement>("#chart-age-comp")!;
    },
    get controllerOrders(): HTMLElement {
      return q<HTMLElement>("#chart-controller-orders")!;
    },
    get spoil(): HTMLElement {
      return q<HTMLElement>("#chart-spoil")!;
    },
    get ageCompFocus(): HTMLElement {
      return q<HTMLElement>("#chart-age-comp-focus")!;
    },
    get controllerOrdersFocus(): HTMLElement {
      return q<HTMLElement>("#chart-controller-orders-focus")!;
    },
    get spoilFocus(): HTMLElement {
      return q<HTMLElement>("#chart-spoil-focus")!;
    },
    get dampedSwDemo(): HTMLElement {
      return q<HTMLElement>("#chart-damped-sw-demo")!;
    },
    get arrivalPrior(): HTMLElement {
      return q<HTMLElement>("#chart-arrival-prior")!;
    },
    get arrivalShift(): HTMLElement {
      return q<HTMLElement>("#chart-arrival-shift")!;
    },
    get arrheniusTemp(): HTMLElement {
      return q<HTMLElement>("#chart-arrhenius-temp")!;
    },
    get gammaPath(): HTMLElement {
      return q<HTMLElement>("#chart-gamma-path")!;
    },
    get pickingVar(): HTMLElement {
      return q<HTMLElement>("#picking-var-chart")!;
    },
    get pnlEconomics(): HTMLElement {
      return q<HTMLElement>("#chart-pnl-economics")!;
    },
    get focusTitle(): HTMLElement {
      return q<HTMLElement>("#focus-title")!;
    },
    get focusBlurb(): HTMLElement {
      return q<HTMLElement>("#focus-blurb")!;
    },
    get focusPane(): HTMLElement {
      return q<HTMLElement>(".tuning-drawer")!;
    },
  };

  let tuningDrawerOpen = false;
  let closeReferenceDrawer: (() => void) | null = null;

  function setTuningDrawerOpen(open: boolean): void {
    tuningDrawerOpen = open;
    if (open) closeReferenceDrawer?.();
    const trigger = q<HTMLButtonElement>("#tuning-drawer-trigger");
    if (trigger) trigger.setAttribute("aria-expanded", open ? "true" : "false");
    renderTuningDrawer();
    if (open) {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => renderActiveFocusPlots());
      });
    }
  }

  function openTuningDrawer(): void {
    if (!tuningDrawerOpen) setTuningDrawerOpen(true);
  }

  const pnlTotalsHost = q<HTMLElement>("#pnl-totals-host");
  const obsControlsHost = q<HTMLElement>("#obs-controls-pane-host");
  const eventsPaneHost = q<HTMLElement>("#events-pane-host");
  const referenceDrawerHost = q<HTMLElement>("#reference-drawer-host");
  const tuningDrawerHost = q<HTMLElement>("#tuning-drawer-host");
  const eventsPaneRoot = eventsPaneHost ? createRoot(eventsPaneHost) : null;
  let spoilageUnavailableRoot: Root | null = null;
  const obsControlsRoot = obsControlsHost ? createRoot(obsControlsHost) : null;
  const referenceDrawerRoot = referenceDrawerHost
    ? createRoot(referenceDrawerHost)
    : null;
  const tuningDrawerRoot = tuningDrawerHost ? createRoot(tuningDrawerHost) : null;
  const operatorBarHost = q<HTMLElement>("#operator-bar-host");
  const operatorBarRoot = operatorBarHost ? createRoot(operatorBarHost) : null;

  const tuningDrawerPortalRef = { current: tuningDrawerHost };

  function renderReferenceDrawer(): void {
    profileSync("renderReferenceDrawer", () => {
      if (referenceDrawerRoot) {
        referenceDrawerRoot.render(
          createElement<ReferenceDrawerProps>(ReferenceDrawer, {
            hideTriggers: true,
            onOpen: () => setTuningDrawerOpen(false),
            registerCloseHandler: (close) => {
              closeReferenceDrawer = close;
            },
          }),
        );
      }
    });
  }

  function renderTuningDrawer(): void {
    profileSync("renderTuningDrawer", () => {
      if (tuningDrawerRoot) {
        tuningDrawerRoot.render(
          createElement<TuningDrawerProps>(TuningDrawer, {
            hideTrigger: true,
            open: tuningDrawerOpen,
            onOpenChange: setTuningDrawerOpen,
            onOpen: () => closeReferenceDrawer?.(),
            portalContainerRef: tuningDrawerPortalRef,
          }),
        );
      }
    });
  }

  function paintPortalDrawers(): void {
    renderReferenceDrawer();
    renderTuningDrawer();
  }

  renderReferenceDrawer();
  renderTuningDrawer();

  const loadingHost = q<HTMLElement>("#studio-loading-host");
  const loadingPortalRef = { current: loadingHost };
  const loadingRoot = loadingHost ? createRoot(loadingHost) : null;

  function renderLoadingDialog(): void {
    if (!loadingRoot) return;
    loadingRoot.render(
      createElement(StudioLoadingDialog, {
        visible: loadingDialogVisible,
        message: loadingMessage,
        portalContainerRef: loadingPortalRef,
      }),
    );
    const shell = q<HTMLElement>(".shell.studio");
    if (shell) {
      if (loadingDialogVisible) {
        shell.setAttribute("aria-busy", "true");
      } else {
        shell.removeAttribute("aria-busy");
      }
    }
  }

  const delayedLoading = createDelayedLoadingHandle((visible) => {
    loadingDialogVisible = visible;
    renderLoadingDialog();
  });

  function beginStudioLoading(message: string): void {
    loadingMessage = message;
    renderLoadingDialog();
    delayedLoading.begin();
  }

  function endStudioLoading(): void {
    delayedLoading.end();
  }

  renderLoadingDialog();

  async function fetchEvents(gen: number): Promise<void> {
    if (typeof adapter.events !== "function" || !schedule) return;
    const sinceDay = Math.max(1, vm.episode_day - 5);
    const key = `${vm.episode_day}:${channelsCacheKey(vm.config.obs_channels)}:${sinceDay}`;
    if (key === lastEventsKey) return;
    lastEventsKey = key;
    if (eventDays.length === 0) {
      eventsLoading = true;
    } else {
      eventsRefreshing = true;
    }
    try {
      const result = await adapter.events({ since_day: sinceDay });
      if (gen !== frameGen) return;
      eventDays = result.days ?? [];
    } catch {
      if (gen !== frameGen) return;
      if (eventDays.length === 0) eventDays = [];
    } finally {
      if (gen !== frameGen) return;
      eventsLoading = false;
      eventsRefreshing = false;
    }
  }

  async function commitFrame(): Promise<void> {
    const gen = ++frameGen;
    await profileAsync("fetchEvents", () => fetchEvents(gen));
    if (gen !== frameGen) return;
    renderAll();
  }

  function renderMetricsPane(): void {
    profileSync("renderMetricsPane", () => {
      if (pnlTotalsHost) {
        profileSync("renderMetricsPane.pnlTotals", () =>
          renderPnLTotals(pnlTotalsHost, vm),
        );
      }
      profileSync("renderMetricsPane.pnlTimeseries", () =>
        renderPnLTimeseries(els.pnlEconomics, vm.pnl_series, METRICS_STRIP_HEIGHT),
      );
    });
  }

  function maskedEventDays(): ReturnType<typeof applyMask>[] {
    const mask = vm.config.obs_channels
      ? maskFromChannels(vm.config.obs_channels)
      : maskFor(vm.config.obs_scenario);
    return eventDays.map((day) => applyMask(day as RichObsWire, mask));
  }

  function renderEventsPane(): void {
    profileSync("renderEventsPane", () => {
      if (!eventsPaneRoot) return;
      eventsPaneRoot.render(
        createElement(EventsPane, {
          vm: {
            episode_day: vm.episode_day,
            config: vm.config,
          },
          schedule,
          events: maskedEventDays(),
          loading: eventsLoading,
          refreshing: eventsRefreshing,
        }),
      );
    });
  }
  const dayInspectorHost = q<HTMLElement>("#day-inspector-host");
  const dayInspectorRoot = dayInspectorHost ? createRoot(dayInspectorHost) : null;

  function renderLogisticsCalendar(): void {
    if (!plotVisible("plot-logistics-calendar")) return;
    const calHost = q<HTMLElement>("#week-calendar");
    if (!calHost) return;
    const previewSchedule =
      vm.config.delivery_weekdays?.length > 0
        ? scheduleFromConfig(vm.config)
        : schedule;
    const sched =
      previewSchedule ??
      scheduleFromConfig({
        delivery_weekdays: vm.config.delivery_weekdays ?? [0, 2, 4],
        lead_time: vm.config.lead_time,
      });
    renderWeekCalendar(calHost, sched, {
      disabled: catchingUp,
      onToggleDelivery: (weekday) => {
        const current = vm.config.delivery_weekdays ?? [0, 2, 4];
        const next = toggleDeliveryDay(current, weekday);
        if (JSON.stringify(next) !== JSON.stringify(current)) {
          vm = projector.setConfig({ delivery_weekdays: next });
          sectionControlsApi?.update(controlsState());
          renderLogisticsCalendar();
          if (vm.config_dirty && autopilot?.isRunning()) {
            autopilot.pause();
            syncAutopilotChrome();
          }
        }
      },
    });
    const hint = q<HTMLElement>("#week-calendar-hint");
    if (hint) {
      hint.hidden = !vm.config_dirty;
    }
  }

  function renderObsControlsPane(): void {
    profileSync("renderObsControlsPane", () => {
      if (obsControlsRoot) {
        obsControlsRoot.render(
          createElement(ObsControlsPane, {
            vm,
            showTruth,
            catchingUp,
            onSetObsChannels: (ch) => railHandlers.onSetObsChannels(ch),
            onSetObsPreset: (id) => railHandlers.onSetObsPreset(id),
            onShowTruthChange: (on) => railHandlers.onShowTruthChange(on),
          }),
        );
      }
    });
  }

  function renderOperatorBar(): void {
    profileSync("renderOperatorBar", () => {
      if (operatorBarRoot) {
        operatorBarRoot.render(
          createElement(OperatorBar, {
            vm,
            catchingUp,
            advancing,
            autopilotRunning: autopilot?.isRunning() ?? false,
            orderQty,
            onAdvance: () => railHandlers.onAdvance(),
            onReset: () => railHandlers.onReset(),
            onAutopilotPlay: () => railHandlers.onAutopilotPlay(),
            onAutopilotPause: () => railHandlers.onAutopilotPause(),
            onOrderChange: (qty) => {
              orderQty = snapOrder(qty);
              sectionControlsApi?.update(controlsState());
              paintPortalDrawers();
              renderOperatorBar();
            },
          }),
        );
      }
    });
  }

  function renderDayInspector(): void {
    if (!dayInspectorRoot) return;
    profileSync("renderDayInspector", () => {
      dayInspectorRoot.render(
        createElement(DayInspector, { day: hoveredDay, point: hoveredPoint, vm }),
      );
    });
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

  function beliefFreshnessHoverFocus(
    source: HoverChartSource,
  ): BeliefFreshnessHoverFocus {
    if (source === "sales") return "sales";
    if (source === "spoilage") return "spoiled";
    return "default";
  }

  function applyHoverStyles(
    day: HoverDay,
    source: HoverChartSource = hoveredChartSource,
  ): void {
    setMarginalHover(els.sales, day);
    setMarginalHover(els.stockout, day);
    setBeliefFreshnessTimeHover(
      els.history,
      day,
      beliefFreshnessHoverFocus(source),
    );
    setSalesDemandHover(els.salesDemand, day);
    setControllerOrdersHover(els.controllerOrders, day);
    setControllerOrdersHover(els.controllerOrdersFocus, day);
    setWasteBarsHover(els.spoil, day);
    setWasteBarsHover(els.spoilFocus, day);
    setPnLHover(els.pnlEconomics, day);
    setFreshnessCompositionHover(els.ageComp, day);
    setFreshnessCompositionHover(els.ageCompFocus, day);
    setDemandHover(els.demand, day);
    setDemandForecastHover(els.demandForecast, day);
  }

  function onHoverDay(
    day: HoverDay,
    point: HoverPoint,
    source: HoverChartSource,
  ): void {
    const sameDay = hoveredDay === day;
    const samePoint =
      (point === null && hoveredPoint === null) ||
      (point !== null &&
        hoveredPoint !== null &&
        point.clientX === hoveredPoint.clientX &&
        point.clientY === hoveredPoint.clientY);
    const sameSource = hoveredChartSource === source;
    if (sameDay && samePoint && sameSource) return;
    hoveredDay = day;
    hoveredPoint = point;
    hoveredChartSource = source;
    els.hoverNote.textContent =
      day == null
        ? "Hover a day to highlight it everywhere"
        : `Day ${day} highlighted`;
    applyHoverStyles(day, source);
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
      units: [],
      unit_exits: [],
      f_at_receipt: null,
    }));
  }

  function syncTruthCaptions(): void {
    qa<HTMLElement>("[data-truth-caption]").forEach((el) => {
      const label = el.querySelector<HTMLElement>("[data-truth-caption-label]");
      if (!label) return;
      const kind = el.dataset.truthCaption;
      if (kind === "belief-lg") {
        label.textContent = "Today's Freshness Distribution";
      }
      if (kind === "age-comp") {
        label.textContent = showTruth
          ? "Historical Freshness Summary (Truth)"
          : "Historical Freshness Summary (Belief)";
      }
      if (kind === "lots") {
        label.textContent =
          !showTruth && vm.history.length > 0
            ? "Historical Freshness Distribution (turn on Omniscience to see unit trajectories)"
            : "Historical Freshness Distribution";
      }
    });
    syncBeliefMaeStats();
  }

  function syncBeliefMaeStats(): void {
    const table = q<HTMLTableElement>("[data-belief-mae-table]");
    if (!table) return;

    const visible = showTruth && vm.live_units.length > 0;
    const todayMeanCell = q<HTMLElement>("[data-belief-mae-today-mean]");
    const todayDistCell = q<HTMLElement>("[data-belief-mae-today-dist]");
    const allMeanCell = q<HTMLElement>("[data-belief-mae-all-mean]");
    const allDistCell = q<HTMLElement>("[data-belief-mae-all-dist]");

    if (!visible || !todayMeanCell || !todayDistCell || !allMeanCell || !allDistCell) {
      table.hidden = true;
      table.removeAttribute("title");
      todayMeanCell?.replaceChildren();
      todayDistCell?.replaceChildren();
      allMeanCell?.replaceChildren();
      allDistCell?.replaceChildren();
      return;
    }

    const flat = vm.belief_history.at(-1)?.flatBelief;
    const todayMeanMae = flat ? currentMeanFAbsError(flat, vm.live_units) : null;
    const todayDistMae = flat
      ? currentDistributionAbsError(flat, vm.live_units)
      : null;

    const meanSummary = meanMeanFAbsErrorOverHistory(
      vm.history,
      vm.belief_history,
    );
    const distSummary = meanDistributionAbsErrorOverHistory(
      vm.history,
      vm.belief_history,
    );

    if (
      todayMeanMae == null ||
      todayDistMae == null ||
      !meanSummary ||
      !distSummary
    ) {
      table.hidden = true;
      table.removeAttribute("title");
      todayMeanCell.replaceChildren();
      todayDistCell.replaceChildren();
      allMeanCell.replaceChildren();
      allDistCell.replaceChildren();
      return;
    }

    table.hidden = false;
    table.title = BELIEF_MAE_TOOLTIP;
    todayMeanCell.textContent = formatMeanFAbsError(todayMeanMae);
    todayDistCell.textContent = formatMeanFAbsError(todayDistMae);
    allMeanCell.textContent = formatMeanFAbsError(meanSummary.meanMae);
    allDistCell.textContent = formatMeanFAbsError(distSummary.meanMae);
  }

  function plotVisible(plotId: string): boolean {
    for (const node of qa<HTMLElement>(`.focus-plot[data-plot="${plotId}"]`)) {
      const block = node.closest(".controls-block") as HTMLElement | null;
      if (block && !block.hidden) return true;
    }
    return false;
  }

  function mountChartIntoHost(chartEl: HTMLElement, hostId: string): void {
    const host = q<HTMLElement>(`#${hostId}`);
    if (host && chartEl.parentElement !== host) {
      host.appendChild(chartEl);
    }
  }

  function mountTuningChartHosts(sectionId: SectionId): void {
    if (sectionId === "demand") {
      mountChartIntoHost(els.demand, "chart-demand-host");
    }
    if (sectionId === "logistics") {
      mountChartIntoHost(els.ageCompFocus, "chart-age-comp-focus-host");
    }
  }

  function liveEffectiveInventory(): number | null {
    if (showTruth) {
      const inv = inventorySeries(vm.history, vm.config);
      const last = inv[inv.length - 1];
      return last ? last.effective : null;
    }
    const belief = vm.belief_history.at(-1);
    if (belief?.flatBelief) {
      return effectiveInventoryFromFlatBelief(belief.flatBelief);
    }
    const inv = inventorySeriesFromBelief(vm.belief_history, vm.config);
    const last = inv[inv.length - 1];
    return last ? last.effective : null;
  }

  function renderDampedSwDemoFocus(): void {
    const previewSchedule =
      vm.config.delivery_weekdays?.length > 0
        ? scheduleFromConfig(vm.config)
        : schedule;
    renderDampedSwDemo(els.dampedSwDemo, {
      alpha: controllerState.alpha,
      rho: controllerState.rho,
      policy: controllerState.policy,
      caseSize: vm.config.case_size,
      demandVm: vm.config.demand_vm,
      demandSummary: vm.demand_summary,
      schedule: previewSchedule,
      episodeDay: vm.episode_day,
      effectiveInventory: liveEffectiveInventory(),
    });
  }

  function ageCompositionInputs(): {
    ageRows: ReturnType<typeof fCompositionSeries>;
    effectiveSeries: { day: number; effective: number }[];
  } {
    const ageRows = showTruth
      ? fCompositionSeries(vm.history)
      : fCompositionSeriesFromBelief(vm.belief_history);
    const invSeries = showTruth
      ? inventorySeries(vm.history, vm.config)
      : inventorySeriesFromBelief(vm.belief_history, vm.config);
    const effectiveSeries = invSeries.map((d) => ({
      day: d.day,
      effective: d.effective,
    }));
    return { ageRows, effectiveSeries };
  }

  function renderAgeCompositionChart(host: HTMLElement, height: number): void {
    const { ageRows, effectiveSeries } = ageCompositionInputs();
    renderFreshnessComposition(
      host,
      vm.history,
      height,
      ageRows,
      effectiveSeries,
    );
  }

  function renderRunStripCharts(): void {
    profileSync("renderRunStripCharts", () => {
      profileSync("renderRunStripCharts.controllerOrders", () =>
        renderControllerOrders(
          els.controllerOrders,
          vm.history,
          METRICS_STRIP_HEIGHT,
        ),
      );
      profileSync("renderRunStripCharts.spoil", () => {
        const spoilSlot = resolveStoreSpoilageSlot({
          scenario: vm.config.obs_scenario,
          channels: vm.config.obs_channels,
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
          return;
        }
        if (spoilageUnavailableRoot) {
          flushSync(() => {
            spoilageUnavailableRoot!.render(null);
          });
        }
        renderWasteBars(
          els.spoil,
          vm.history,
          METRICS_STRIP_HEIGHT,
          wasteBarYMax(vm.history),
        );
      });
    });
  }

  function renderCockpitBelief(): void {
    profileSync("renderCockpitBelief", () => {
      profileSync("renderCockpitBelief.ageComp", () =>
        renderAgeCompositionChart(els.ageComp, METRICS_STRIP_HEIGHT),
      );
      const flat = vm.belief_history.at(-1)?.flatBelief;
      const data = flat
        ? freshnessHistogramDataFromFlat(flat, vm.live_units)
        : emptyFreshnessHistogramData();
      renderFreshnessHistogram(
        els.beliefLg,
        data,
        showTruth,
        BELIEF_HISTOGRAM_HEIGHT,
      );
      els.beliefAgeMarginal.replaceChildren();
    });
  }

  function renderStore() {
    profileSync("renderStore", () => {
      const yMax = profileSync("renderStore.marginalYMax", () => marginalYMax(vm.history));
      profileSync("renderStore.renderMarginal.sales", () =>
        renderMarginal(els.sales, vm.history, "sales", 48, yMax),
      );
      profileSync("renderStore.renderMarginal.stockout", () =>
        renderMarginal(els.stockout, vm.history, "stockout", 48, yMax),
      );
      profileSync("renderStore.beliefFreshnessTime", () =>
        renderBeliefFreshnessTime(
          els.history,
          historyForCharts(),
          vm.belief_history,
          showTruth,
          { height: BELIEF_FRESHNESS_TIME_HEIGHT },
        ),
      );
      profileSync("renderStore.salesDemand", () =>
        renderSalesDemand(
          els.salesDemand,
          vm.history,
          METRICS_STRIP_HEIGHT,
          buildDemandForecastRows(
            salesDemandForecastAnchor(vm.history, vm.episode_day),
            vm.demand_summary,
            vm.config.demand_vm,
          ),
        ),
      );
      renderCockpitBelief();
      renderRunStripCharts();
      profileSync("renderStore.applyHoverStyles", () => applyHoverStyles(hoveredDay));
    });
  }

  const FOCUS_CHART_HEIGHT = 95;

  function renderActiveFocusPlots(): void {
    profileSync("renderActiveFocusPlots", () => {
      renderRunStripCharts();
      if (plotVisible("plot-age-comp")) {
        profileSync("renderActiveFocusPlots.ageCompFocus", () =>
          renderAgeCompositionChart(els.ageCompFocus, FOCUS_CHART_HEIGHT),
        );
      }
      if (plotVisible("plot-demand")) {
        profileSync("renderActiveFocusPlots.demand", () =>
          renderDailyDemand(els.demand, vm.history, 160),
        );
      }
      if (plotVisible("plot-demand-forecast")) {
        profileSync("renderActiveFocusPlots.demandForecast", () =>
          renderDemandForecast(
            els.demandForecast,
            vm.history,
            vm.demand_summary,
            vm.episode_day,
            vm.config.demand_vm,
            160,
          ),
        );
      }
      if (plotVisible("plot-picking-variability")) {
        profileSync("renderActiveFocusPlots.pickingVar", () =>
          renderPickingVariability(els.pickingVar, vm.config.sigma, 95),
        );
      }
      profileSync("renderActiveFocusPlots.logisticsCalendar", () => renderLogisticsCalendar());
      if (plotVisible("plot-arrival-prior")) {
        profileSync("renderActiveFocusPlots.arrivalPrior", () =>
          renderArrivalPrior(
            els.arrivalPrior,
            vm.arrival_summary,
            historyForCharts(),
            160,
            arrivalRugAvailable(
              vm.config.obs_channels ?? channelsForPreset(vm.config.obs_scenario),
              showTruth,
            ),
          ),
        );
      }
      if (plotVisible("plot-arrival-shift")) {
        profileSync("renderActiveFocusPlots.arrivalShift", () =>
          renderArrivalShift(els.arrivalShift, vm.arrival_summary, vm.config.transit_temp_bias_c, 150),
        );
      }
      if (plotVisible("plot-arrhenius-temp")) {
        profileSync("renderActiveFocusPlots.arrheniusTemp", () =>
          renderArrheniusTemp(els.arrheniusTemp, vm.config, 160),
        );
      }
      if (plotVisible("plot-gamma-path")) {
        profileSync("renderActiveFocusPlots.gammaPath", () =>
          renderGammaFreshnessPath(els.gammaPath, vm.config, 170),
        );
      }
      if (plotVisible("plot-damped-sw-demo")) {
        profileSync("renderActiveFocusPlots.dampedSwDemo", () =>
          renderDampedSwDemoFocus(),
        );
      }
    });
  }

  function syncTuningDrawerTabs(): void {
    qa<HTMLButtonElement>(".tuning-dock-tabs [data-section]").forEach((tab) => {
        const selected = tab.dataset.section === activeSection;
        tab.setAttribute("aria-selected", selected ? "true" : "false");
        tab.tabIndex = selected ? 0 : -1;
      });
  }

  function setSection(id: SectionId): void {
    activeSection = id;
    saveSection(id);
    const meta = STUDIO_SECTIONS.find((s) => s.id === id)!;

    syncTuningDrawerTabs();

    els.focusTitle.textContent = meta.label;
    els.focusBlurb.textContent = meta.blurb;
    sectionControlsApi?.showSection(id);

    mountTuningChartHosts(id);

    els.focusPane.classList.remove("focus-flash");
    void els.focusPane.offsetWidth;
    els.focusPane.classList.add("focus-flash");

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
    profileSync("renderAll", () => {
      profileSync("syncTruthCaptions", () => syncTruthCaptions());
      renderStore();
      renderActiveFocusPlots();
      renderDayInspector();
      renderMetricsPane();
      renderEventsPane();
      renderObsControlsPane();
      renderOperatorBar();
      paintPortalDrawers();
      orderQty = snapOrder(orderQty);
      const state = controlsState();
      profileSync("sectionControlsApi.update", () =>
        sectionControlsApi?.update(state),
      );
      profileSync("wireDemandPreview", () => wireDemandPreview());
    });
  }

  function wireDemandPreview(): void {
    const slider = q<HTMLInputElement>("#demand_mu");
    if (!slider || slider.dataset.previewBound === "1") return;
    slider.dataset.previewBound = "1";
    bindDemandSliderPreview({
      chartHost: els.demand,
      forecastHost: els.demandForecast,
      slider,
      vmSlider: q<HTMLInputElement>("#demand_vm") ?? undefined,
      projector,
      schedule,
    });
  }

  async function advanceEpisode(): Promise<void> {
    const profiling = isAdvanceProfiling();
    const advanceT0 = profiling ? performance.now() : 0;
    let engineStepNMs = 0;
    try {
      if (vm.episode_day >= EPISODE_HORIZON) {
        return;
      }
      if (!schedule) {
        throw new Error("schedule missing — init/reset before advance");
      }
      advancing = true;
      renderOperatorBar();
      beginStudioLoading("Advancing…");
      const orders = buildStepNOrders(vm.episode_day, orderQty, schedule);
      const engineT0 = performance.now();
      const deltas = await adapter.step_n(orders);
      engineStepNMs = performance.now() - engineT0;
      for (const delta of deltas) {
        vm = projector.applyDelta(delta);
      }
      if (deltas.length > 0) {
        const completed = deltas[deltas.length - 1]!.episode_day;
        vm = { ...vm, episode_day: completed + 1 };
      }
      onHoverDay(null, null, null);
      await commitFrame();
      if (studioTeardown) return;
    } catch (err) {
      reportStudioAdapterError(
        `Advance failed: ${formatAdapterError(err)}`,
        studioErrorEl,
        err,
      );
    } finally {
      if (profiling) {
        recordAdvanceSample(
          buildAdvanceSample(
            performance.now() - advanceT0,
            engineStepNMs,
            getRenderProfileReport(),
          ),
        );
      }
      advancing = false;
      endStudioLoading();
      renderOperatorBar();
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
      onHoverDay(null, null, null);
      await commitFrame();
      if (studioTeardown) return;
    } catch (err) {
      reportStudioAdapterError(
        `Reset failed: ${formatAdapterError(err)}`,
        studioErrorEl,
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
    applyDelta: async (delta) => {
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
      onHoverDay(null, null, null);
      await commitFrame();
    },
    getOpts: controllerToActOpts,
    getIntervalMs: () => controllerState.intervalMs,
    isConfigDirty: () => vm.config_dirty,
    onError(err) {
      reportStudioAdapterError(
        `Autopilot failed: ${formatAdapterError(err)}`,
        studioErrorEl,
        err,
      );
      syncAutopilotChrome();
    },
    onTick(_delta) {
      // Loop may pause for config_dirty after this callback returns.
      queueMicrotask(syncAutopilotChrome);
    },
  });

  let sectionControlsApi!: ReturnType<typeof mountSectionControls>;
  let sectionControlsMounted = false;
  let sectionControlsMountCancelled = false;
  let studioTeardown = false;
  let sectionControlsMountRaf = 0;

  function mountSectionControlsOnce(): void {
    const host = q<HTMLElement>("#section-controls");
    if (!host) return;
    if (sectionControlsMounted && host.childElementCount > 0) return;
    sectionControlsMounted = true;
    sectionControlsApi = mountSectionControls(
      host,
      controlsState(),
      {
        onEconomicsChange(partial: Partial<Economics>) {
          // Local reproject only — never round-trip to the engine.
          vm = projector.setEconomics(partial);
          renderMetricsPane();
          sectionControlsApi.update(controlsState());
        },
        onConfigChange(partial: Partial<SimConfig>) {
          // Stage knobs locally; engine applies on next reset/init (no Mock setConfig).
          vm = projector.setConfig(partial);
          if (partial.case_size != null) {
            orderQty = snapOrder(orderQty);
          }
          sectionControlsApi.update(controlsState());
          paintPortalDrawers();
          renderOperatorBar();
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
          renderActiveFocusPlots();
        },
      },
      (caseSize) => {
        orderQty = snapOrder(orderQty);
        sectionControlsApi.update({
          ...controlsState(),
          orderQty,
          config: { ...vm.config, case_size: caseSize },
        });
        renderObsControlsPane();
      },
      controllerState,
    );
    wireTuningDockTabs();

    const tuningTrigger = q<HTMLButtonElement>("#tuning-drawer-trigger");
    if (tuningTrigger && tuningTrigger.dataset.bound !== "1") {
      tuningTrigger.dataset.bound = "1";
      tuningTrigger.addEventListener("click", () => {
        setTuningDrawerOpen(!tuningDrawerOpen);
      });
    }
  }

  function scheduleSectionControlsMount(): void {
    let attempts = 0;
    const attempt = () => {
      if (sectionControlsMountCancelled) return;
      paintPortalDrawers();
      const host = q<HTMLElement>("#section-controls");
      if (!host) {
        attempts += 1;
        if (attempts > 120) {
          throw new Error(
            "Tuning drawer #section-controls host missing after portal paint",
          );
        }
        sectionControlsMountRaf = requestAnimationFrame(attempt);
        return;
      }
      mountSectionControlsOnce();
    };
    attempt();
  }

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
    // tick() may pause synchronously when config_dirty; sync after it runs.
    queueMicrotask(syncAutopilotChrome);
  };
  railHandlers.onAutopilotPause = () => {
    autopilot.pause();
    syncAutopilotChrome();
  };
  async function applyObsSelection(
    channels: ObsChannels,
    explicitPreset?: ScenarioId,
  ): Promise<void> {
    const obs_scenario = resolveDisplayObsScenario(channels, explicitPreset);
    const setCh =
      adapter.set_obs_channels?.bind(adapter) ??
      adapter.setObsChannels?.bind(adapter);
    if (typeof setCh !== "function") {
      vm = projector.setConfig({ obs_channels: channels, obs_scenario });
      sectionControlsApi.update(controlsState());
      lastEventsKey = "";
      await commitFrame();
      return;
    }
    const resumeAfter = autopilot.isRunning();
    if (resumeAfter) {
      autopilot.pause();
      syncAutopilotChrome();
    }
    catchingUp = true;
    sectionControlsApi.update(controlsState());
    renderObsControlsPane();
    renderOperatorBar();
    beginStudioLoading("Updating observations…");
    try {
      const snap = (await engineStatus.follow(setCh(channels))) as Snapshot;
      vm = projector.patchEngineState(snap);
      vm = projector.setConfig({ obs_channels: channels, obs_scenario });
      lastEventsKey = "";
      await commitFrame();
      if (studioTeardown) return;
    } catch (err) {
      reportStudioAdapterError(
        `set_obs_channels failed: ${formatAdapterError(err)}`,
        studioErrorEl,
        err,
      );
    } finally {
      catchingUp = false;
      renderOperatorBar();
      endStudioLoading();
      sectionControlsApi.update(controlsState());
      renderObsControlsPane();
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
    await applyObsSelection(channels);
  };
  railHandlers.onShowTruthChange = (show) => {
    showTruth = show;
    saveShowTruth(show);
    app.classList.toggle("studio--show-truth", show);
    renderAll();
  };

  const onKeydown = (event: KeyboardEvent) => {
    const tag = (event.target as HTMLElement | null)?.tagName;
    if (tag === "INPUT" || tag === "TEXTAREA") return;

    const idx = STUDIO_SECTIONS.findIndex((s) => s.id === activeSection);
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      event.preventDefault();
      openTuningDrawer();
      setSection(STUDIO_SECTIONS[(idx + 1) % STUDIO_SECTIONS.length]!.id);
      return;
    }
    if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      event.preventDefault();
      openTuningDrawer();
      setSection(
        STUDIO_SECTIONS[(idx - 1 + STUDIO_SECTIONS.length) % STUDIO_SECTIONS.length]!
          .id,
      );
      return;
    }
    const n = Number(event.key);
    if (n >= 1 && n <= STUDIO_SECTIONS.length) {
      event.preventDefault();
      openTuningDrawer();
      setSection(STUDIO_SECTIONS[n - 1]!.id);
    }
  };

  function wireTuningDockTabs(): void {
    qa<HTMLButtonElement>(".tuning-dock-tabs [data-section]").forEach((tab) => {
        if (tab.dataset.bound === "1") return;
        tab.dataset.bound = "1";
        tab.addEventListener("click", () => {
          const id = tab.dataset.section as SectionId | undefined;
          if (id) {
            openTuningDrawer();
            setSection(id);
          }
        });
      });
  }

  async function bootstrap(): Promise<void> {
    if (bootstrapped) return;
    bootstrapped = true;
    try {
      const snap = await engineStatus.follow(adapter.init({ ...vm.config }));
      if (studioTeardown) return;
      captureSchedule(snap);
      vm = projector.applySnapshot(snap);
      projector.markConfigApplied();
      setSection(activeSection);
      await commitFrame();
      if (studioTeardown) return;
    } catch (err) {
      reportStudioAdapterError(
        `Init failed: ${formatAdapterError(err)}`,
        studioErrorEl,
        err,
      );
    }
  }

  scheduleSectionControlsMount();
  flushSync(() => {
    paintPortalDrawers();
  });
  mountSectionControlsOnce();
  const sectionControlsMountTimer = setTimeout(() => {
    mountSectionControlsOnce();
  }, 0);
  app.addEventListener("keydown", onKeydown);
  void bootstrap();

  studioAdvanceOnce = advanceEpisode;
  if (typeof window !== "undefined") {
    window.__studioProfileAdvance = (steps = 5) => studioProfileAdvanceSteps(steps);
  }

  const onResize = () => {
    renderStore();
    renderActiveFocusPlots();
  };
  window.addEventListener("resize", onResize);
  return () => {
    studioTeardown = true;
    sectionControlsMountCancelled = true;
    clearTimeout(sectionControlsMountTimer);
    cancelAnimationFrame(sectionControlsMountRaf);
    app.removeEventListener("keydown", onKeydown);
    window.removeEventListener("resize", onResize);
    eventsPaneRoot?.unmount();
    obsControlsRoot?.unmount();
    operatorBarRoot?.unmount();
    referenceDrawerRoot?.unmount();
    tuningDrawerRoot?.unmount();
    loadingRoot?.unmount();
    dayInspectorRoot?.unmount();
    spoilageUnavailableRoot?.unmount();
    delete app.dataset.studioInit;
  };
}
