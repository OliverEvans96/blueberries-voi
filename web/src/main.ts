import "./styles.css";
import { MockAdapter } from "./mock/adapter";
import { renderHistory, setHistoryHover } from "./charts/history";
import { renderMarginal, setMarginalHover } from "./charts/marginals";
import { renderPnLTimeseries, setPnLHover } from "./charts/pnlTimeseries";
import { renderPnLTotals } from "./charts/pnlTotals";
import { renderBeliefAgeCount } from "./charts/beliefAgeCount";
import { renderSurvival } from "./charts/survival";
import { renderDemandDist } from "./charts/demandDist";
import {
  renderAgeComposition,
  renderInventoryTarget,
} from "./charts/inventoryTarget";
import { renderSalesDemand } from "./charts/salesDemand";
import { renderGhostDeltas } from "./charts/ghostDeltas";
import {
  controlsFromVm,
  mountPlayChrome,
  mountSectionControls,
} from "./controls";
import { attachLinkedHover } from "./hoverLink";
import {
  STUDIO_SECTIONS,
  loadSection,
  saveSection,
  type SectionId,
} from "./sections";
import type { Economics, HoverDay, SimConfig, ViewModel } from "./types";

const app = document.querySelector("#app");
if (!app) throw new Error("#app missing");

const navHtml = STUDIO_SECTIONS.map(
  (s, i) => `
  <button type="button" class="section-nav-item" data-section="${s.id}" data-index="${i}">
    <span class="section-nav-index">${i + 1}</span>
    <span class="section-nav-text">
      <span class="section-nav-label">${s.label}</span>
      <span class="section-nav-blurb">${s.blurb}</span>
    </span>
  </button>
`,
).join("");

app.innerHTML = `
  <div class="shell studio">
    <header class="hero">
      <div class="brand">Cold Case Ledger</div>
      <h1>Blueberry inventory studio</h1>
      <p class="lede">
        Walk one idea at a time — order the store, then open Pricing, Physics,
        Demand, Logistics, or Belief to see how each knob teaches through its plots.
      </p>
    </header>

    <div class="studio-layout">
      <main class="store">
        <section class="panel panel-stage" id="linked-charts">
          <div class="panel-head">
            <h2>The store</h2>
            <span class="panel-note" id="hover-note">Hover a day to highlight it everywhere</span>
          </div>
          <div class="legend-inline store-legend">
            <span class="chip chip-sales">Sales</span>
            <span class="chip chip-lots">Lots (size ∝ qty)</span>
            <span class="chip chip-spoil">Spoilage</span>
          </div>
          <div class="chart-stack">
            <div class="chart-caption">Units sold</div>
            <div id="chart-sales" class="chart"></div>
            <div class="chart-caption">Lots · day × age</div>
            <div id="chart-history" class="chart"></div>
            <div class="chart-caption">Units spoiled</div>
            <div id="chart-spoil" class="chart"></div>
          </div>
        </section>
        <div id="ghost-deltas" class="ghost-slot"></div>
      </main>

      <aside class="focus-column">
        <section class="panel play-panel">
          <div class="panel-head"><h2>Run</h2></div>
          <div id="play-chrome"></div>
          <div class="pnl-chrome">
            <div id="chart-pnl-totals"></div>
            <div class="chart-caption impact-caption">Profit sparkline</div>
            <div id="chart-pnl-spark" class="chart"></div>
          </div>
        </section>

        <div class="focus-row">
          <nav class="section-nav panel" aria-label="Studio sections">
            ${navHtml}
            <p class="section-nav-hint">Keys 1–6 or ← →</p>
          </nav>

          <section class="panel focus-pane" id="focus-pane">
            <div class="focus-header">
              <h2 id="focus-title">Play</h2>
              <p class="focus-blurb" id="focus-blurb"></p>
            </div>
            <div id="section-controls"></div>
            <div class="focus-plots">
              <div class="focus-plot" data-plot="plot-belief" hidden>
                <div class="chart-caption impact-caption">Belief vs truth</div>
                <div id="chart-belief" class="chart"></div>
              </div>
              <div class="focus-plot" data-plot="plot-sales-demand" hidden>
                <div class="chart-caption impact-caption">Sales vs demand</div>
                <div id="chart-sales-demand" class="chart"></div>
              </div>
              <div class="focus-plot" data-plot="plot-pnl" hidden>
                <div class="chart-caption impact-caption">Revenue · cost · profit</div>
                <div id="chart-pnl-series" class="chart"></div>
              </div>
              <div class="focus-plot" data-plot="plot-survival" hidden>
                <div class="chart-caption impact-caption">Survival + lot rug</div>
                <div id="chart-survival" class="chart"></div>
              </div>
              <div class="focus-plot" data-plot="plot-demand" hidden>
                <div class="chart-caption impact-caption">Demand + coverage</div>
                <div id="chart-demand" class="chart"></div>
              </div>
              <div class="focus-plot" data-plot="plot-inventory" hidden>
                <div class="chart-caption impact-caption">Inventory vs base-stock</div>
                <div id="chart-inventory" class="chart"></div>
              </div>
              <div class="focus-plot" data-plot="plot-age-comp" hidden>
                <div class="chart-caption impact-caption">On-hand by age band</div>
                <div id="chart-age-comp" class="chart"></div>
              </div>
              <div class="focus-plot" data-plot="plot-belief-lg" hidden>
                <div class="chart-caption impact-caption">Belief heatmap · truth overlay</div>
                <div id="chart-belief-lg" class="chart"></div>
              </div>
            </div>
          </section>
        </div>
      </aside>
    </div>

    <footer class="foot">
      Fake data studio · blueberries-voi · D3 + Vite
    </footer>
  </div>
`;

const adapter = new MockAdapter();
let vm: ViewModel = adapter.init();
let orderQty = adapter.snapOrder(24);
let hoveredDay: HoverDay = null;
let activeSection: SectionId = loadSection();

const els = {
  linked: document.querySelector("#linked-charts") as HTMLElement,
  sales: document.querySelector("#chart-sales") as HTMLElement,
  history: document.querySelector("#chart-history") as HTMLElement,
  spoil: document.querySelector("#chart-spoil") as HTMLElement,
  pnlSeries: document.querySelector("#chart-pnl-series") as HTMLElement,
  pnlSpark: document.querySelector("#chart-pnl-spark") as HTMLElement,
  pnlTotals: document.querySelector("#chart-pnl-totals") as HTMLElement,
  belief: document.querySelector("#chart-belief") as HTMLElement,
  beliefLg: document.querySelector("#chart-belief-lg") as HTMLElement,
  hoverNote: document.querySelector("#hover-note") as HTMLElement,
  playChrome: document.querySelector("#play-chrome") as HTMLElement,
  sectionControls: document.querySelector("#section-controls") as HTMLElement,
  survival: document.querySelector("#chart-survival") as HTMLElement,
  demand: document.querySelector("#chart-demand") as HTMLElement,
  salesDemand: document.querySelector("#chart-sales-demand") as HTMLElement,
  inventory: document.querySelector("#chart-inventory") as HTMLElement,
  ageComp: document.querySelector("#chart-age-comp") as HTMLElement,
  ghostDeltas: document.querySelector("#ghost-deltas") as HTMLElement,
  focusTitle: document.querySelector("#focus-title") as HTMLElement,
  focusBlurb: document.querySelector("#focus-blurb") as HTMLElement,
  focusPane: document.querySelector("#focus-pane") as HTMLElement,
};

function applyHoverStyles(day: HoverDay): void {
  setMarginalHover(els.sales, day);
  setHistoryHover(els.history, day);
  setMarginalHover(els.spoil, day);
  if (!els.pnlSeries.closest(".focus-plot")?.hasAttribute("hidden")) {
    setPnLHover(els.pnlSeries, day);
  }
}

function onHoverDay(day: HoverDay): void {
  if (hoveredDay === day) return;
  hoveredDay = day;
  els.hoverNote.textContent =
    day == null
      ? "Hover a day to highlight it everywhere"
      : `Day ${day} highlighted`;
  applyHoverStyles(day);
}

attachLinkedHover(els.linked, () => vm.history.map((d) => d.day), {
  onDay: onHoverDay,
});

function plotVisible(plotId: string): boolean {
  const node = document.querySelector(
    `.focus-plot[data-plot="${plotId}"]`,
  ) as HTMLElement | null;
  return !!node && !node.hidden;
}

function renderStore(): void {
  renderMarginal(els.sales, vm.history, "sales", 72);
  renderHistory(els.history, vm.history, { height: 220 });
  renderMarginal(els.spoil, vm.history, "spoilage", 86, vm.ghost);
  applyHoverStyles(hoveredDay);
}

function renderChrome(): void {
  renderPnLTotals(els.pnlTotals, vm);
  renderPnLTimeseries(els.pnlSpark, vm.pnl_series, 118, vm.ghost);
  renderGhostDeltas(els.ghostDeltas, vm.ghost_deltas);
}

function renderActiveFocusPlots(): void {
  if (plotVisible("plot-belief")) {
    renderBeliefAgeCount(els.belief, vm.belief, vm.live_lots, 200);
  }
  if (plotVisible("plot-belief-lg")) {
    renderBeliefAgeCount(els.beliefLg, vm.belief, vm.live_lots, 280);
  }
  if (plotVisible("plot-sales-demand")) {
    renderSalesDemand(els.salesDemand, vm.history, 130);
  }
  if (plotVisible("plot-inventory")) {
    renderInventoryTarget(els.inventory, vm.history, vm.config, 170);
  }
  if (plotVisible("plot-age-comp")) {
    renderAgeComposition(els.ageComp, vm.history, 140);
  }
  if (plotVisible("plot-pnl")) {
    renderPnLTimeseries(els.pnlSeries, vm.pnl_series, 160, vm.ghost);
    applyHoverStyles(hoveredDay);
  }
  if (plotVisible("plot-survival")) {
    renderSurvival(els.survival, vm.config, vm.live_lots, 160);
  }
  if (plotVisible("plot-demand")) {
    renderDemandDist(els.demand, vm.config, vm.on_hand, vm.effective_inv, 160);
  }
}

function setSection(id: SectionId): void {
  activeSection = id;
  saveSection(id);
  const meta = STUDIO_SECTIONS.find((s) => s.id === id)!;

  document.querySelectorAll<HTMLButtonElement>(".section-nav-item").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.section === id);
  });

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
}

function renderAll(): void {
  renderStore();
  renderChrome();
  renderActiveFocusPlots();
  orderQty = adapter.snapOrder(orderQty);
  const state = controlsFromVm(vm, orderQty);
  playChromeApi.update(state);
  sectionControlsApi.update(state);
}

const playChromeApi = mountPlayChrome(
  els.playChrome,
  controlsFromVm(vm, orderQty),
  {
    onOrderChange(qty) {
      orderQty = qty;
    },
    onAdvance() {
      vm = adapter.step({ order_qty: orderQty });
      onHoverDay(null);
      renderAll();
    },
    onReset() {
      vm = adapter.reset();
      orderQty = adapter.snapOrder(orderQty);
      onHoverDay(null);
      renderAll();
    },
  },
);

const sectionControlsApi = mountSectionControls(
  els.sectionControls,
  controlsFromVm(vm, orderQty),
  {
    onEconomicsChange(partial: Partial<Economics>) {
      vm = adapter.setEconomics(partial);
      renderChrome();
      if (plotVisible("plot-pnl")) {
        renderPnLTimeseries(els.pnlSeries, vm.pnl_series, 160, vm.ghost);
        applyHoverStyles(hoveredDay);
      }
      sectionControlsApi.update(controlsFromVm(vm, orderQty));
    },
    onConfigChange(partial: Partial<SimConfig>) {
      vm = adapter.setConfig(partial);
      if (partial.case_size != null) {
        orderQty = adapter.snapOrder(orderQty);
        playChromeApi.update(controlsFromVm(vm, orderQty));
      }
      playChromeApi.update(controlsFromVm(vm, orderQty));
      sectionControlsApi.update(controlsFromVm(vm, orderQty));
      renderActiveFocusPlots();
    },
  },
  (caseSize) => {
    orderQty = adapter.snapOrder(orderQty);
    playChromeApi.setOrderFromCaseChange(orderQty, caseSize);
  },
);

document.querySelectorAll<HTMLButtonElement>(".section-nav-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    const id = btn.dataset.section as SectionId;
    setSection(id);
  });
});

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

setSection(activeSection);
renderAll();

window.addEventListener("resize", () => {
  renderStore();
  renderChrome();
  renderActiveFocusPlots();
});
