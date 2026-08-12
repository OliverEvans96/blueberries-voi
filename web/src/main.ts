import "./styles.css";
import { MockAdapter } from "./mock/adapter";
import { renderHistory, setHistoryHover } from "./charts/history";
import { renderMarginal, setMarginalHover } from "./charts/marginals";
import { renderPnLTimeseries, setPnLHover } from "./charts/pnlTimeseries";
import { renderPnLTotals } from "./charts/pnlTotals";
import { renderBeliefAgeCount } from "./charts/beliefAgeCount";
import { controlsFromVm, mountControls } from "./controls";
import { attachLinkedHover } from "./hoverLink";
import type { Economics, HoverDay, SimConfig, ViewModel } from "./types";

const app = document.querySelector("#app");
if (!app) throw new Error("#app missing");

app.innerHTML = `
  <div class="shell">
    <header class="hero">
      <div class="brand">Cold Case Ledger</div>
      <h1>Blueberry inventory simulator</h1>
      <p class="lede">
        Mock rolling history of lots, sales and spoilage, live P&amp;L, and a
        fake age×count belief field. Tune physics and demand, then reset or
        advance — no Python runtime.
      </p>
    </header>

    <div class="layout">
      <main class="stage">
        <div class="linked-charts" id="linked-charts">
          <section class="panel panel-stage">
            <div class="panel-head">
              <h2>Rolling inventory</h2>
              <div class="legend-inline">
                <span class="chip chip-sales">Sales</span>
                <span class="chip chip-lots">Lots (size ∝ qty)</span>
                <span class="chip chip-spoil">Spoilage</span>
              </div>
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

          <section class="panel panel-stage">
            <div class="panel-head">
              <h2>P&amp;L timeseries</h2>
              <span class="panel-note" id="hover-note">Hover a day to highlight it everywhere</span>
            </div>
            <div id="chart-pnl-series" class="chart"></div>
          </section>
        </div>
      </main>

      <aside class="rail">
        <section class="panel panel-controls">
          <div class="panel-head"><h2>Controls</h2></div>
          <div id="controls"></div>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>P&amp;L totals</h2></div>
          <div id="chart-pnl-totals"></div>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Belief · age × count</h2>
            <span class="panel-note" id="belief-note">Scenario P1</span>
          </div>
          <div id="chart-belief" class="chart"></div>
        </section>
      </aside>
    </div>

    <footer class="foot">
      Fake data mockup · blueberries-voi · D3 + Vite
    </footer>
  </div>
`;

const adapter = new MockAdapter();
let vm: ViewModel = adapter.init();
let orderQty = adapter.snapOrder(24);
let hoveredDay: HoverDay = null;

const els = {
  linked: document.querySelector("#linked-charts") as HTMLElement,
  sales: document.querySelector("#chart-sales") as HTMLElement,
  history: document.querySelector("#chart-history") as HTMLElement,
  spoil: document.querySelector("#chart-spoil") as HTMLElement,
  pnlSeries: document.querySelector("#chart-pnl-series") as HTMLElement,
  pnlTotals: document.querySelector("#chart-pnl-totals") as HTMLElement,
  belief: document.querySelector("#chart-belief") as HTMLElement,
  beliefNote: document.querySelector("#belief-note") as HTMLElement,
  hoverNote: document.querySelector("#hover-note") as HTMLElement,
  controls: document.querySelector("#controls") as HTMLElement,
};

function applyHoverStyles(day: HoverDay): void {
  setMarginalHover(els.sales, day);
  setHistoryHover(els.history, day);
  setMarginalHover(els.spoil, day);
  setPnLHover(els.pnlSeries, day);
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

attachLinkedHover(
  els.linked,
  () => vm.history.map((d) => d.day),
  { onDay: onHoverDay },
);

function renderDataCharts(): void {
  renderMarginal(els.sales, vm.history, "sales", 78);
  renderHistory(els.history, vm.history, { height: 230 });
  renderMarginal(els.spoil, vm.history, "spoilage", 90);
  renderPnLTimeseries(els.pnlSeries, vm.pnl_series, 150);
  applyHoverStyles(hoveredDay);
}

function renderAll(): void {
  renderDataCharts();
  renderPnLTotals(els.pnlTotals, vm);
  renderBeliefAgeCount(els.belief, vm.belief, 270);
  els.beliefNote.textContent = `Scenario ${vm.config.obs_scenario}`;
  orderQty = adapter.snapOrder(orderQty);
  controlsApi.update(controlsFromVm(vm, orderQty));
}

const controlsApi = mountControls(
  els.controls,
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
    onEconomicsChange(partial: Partial<Economics>) {
      vm = adapter.setEconomics(partial);
      renderPnLTotals(els.pnlTotals, vm);
      renderPnLTimeseries(els.pnlSeries, vm.pnl_series, 150);
      applyHoverStyles(hoveredDay);
      controlsApi.update(controlsFromVm(vm, orderQty));
    },
    onConfigChange(partial: Partial<SimConfig>) {
      vm = adapter.setConfig(partial);
      if (partial.case_size != null) {
        orderQty = adapter.snapOrder(orderQty);
      }
      if (partial.obs_scenario != null) {
        renderBeliefAgeCount(els.belief, vm.belief, 270);
        els.beliefNote.textContent = `Scenario ${vm.config.obs_scenario}`;
      }
      controlsApi.update(controlsFromVm(vm, orderQty));
    },
  },
);

renderAll();

window.addEventListener("resize", () => {
  renderDataCharts();
  renderBeliefAgeCount(els.belief, vm.belief, 270);
});
