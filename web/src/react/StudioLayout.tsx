import { STUDIO_SECTIONS } from "../sections";
import { D3ChartHost } from "./D3ChartHost";

/** Static studio shell — pixel parity with legacy main.ts innerHTML (T-121). */
export function StudioLayout() {
  return (
    <div className="shell studio">
      <header className="hero">
        <div className="hero-top">
          <div className="brand">Cold Case Ledger</div>
          <span
            id="engine-status"
            className="engine-status"
            data-status="loading"
            role="status"
            aria-live="polite"
          >
            <span className="engine-status-dot" aria-hidden="true" />
            <span className="engine-status-label">Loading</span>
          </span>
        </div>
        <h1>Blueberry inventory studio</h1>
        <p className="lede">
          Walk one idea at a time — order the store, then open Pricing, Physics,
          Demand, Logistics, Arrival, Belief, or Controller to see how each knob
          teaches through its plots.
        </p>
      </header>

      <div className="studio-layout">
        <main className="store">
          <section className="panel panel-stage" id="linked-charts">
            <div className="panel-head">
              <h2>The store</h2>
              <span className="panel-note" id="hover-note">
                Hover a day to highlight it everywhere
              </span>
            </div>
            <div className="legend-inline store-legend">
              <span className="chip chip-sales">Sales</span>
              <span className="chip chip-lots">Lots (size ∝ qty)</span>
              <span className="chip chip-spoil">Spoilage</span>
              <span className="chip chip-missed">Missed</span>
            </div>
            <div className="chart-stack">
              <div className="chart-caption">Units sold</div>
              <D3ChartHost id="chart-sales" className="chart" />
              <div className="chart-caption">Missed sales</div>
              <D3ChartHost id="chart-stockout" className="chart" />
              <div className="chart-caption" data-truth-caption="lots">
                Lots · day × age
              </div>
              <D3ChartHost id="chart-history" className="chart" />
              <div className="chart-caption">Units spoiled</div>
              <D3ChartHost id="chart-spoil" className="chart" />
            </div>
          </section>
        </main>

        <aside className="focus-column">
          <section className="panel play-panel">
            <div className="panel-head">
              <h2>Run</h2>
            </div>
            <div id="play-chrome" />
            <div className="pnl-chrome">
              <D3ChartHost id="chart-pnl-totals" />
              <div className="chart-caption impact-caption">Cumulative PnL</div>
              <D3ChartHost id="chart-pnl-spark" className="chart" />
            </div>
          </section>

          <div className="focus-row">
            <nav className="section-nav panel" aria-label="Studio sections">
              {STUDIO_SECTIONS.map((s, i) => (
                <button
                  key={s.id}
                  type="button"
                  className="section-nav-item"
                  data-section={s.id}
                  data-index={String(i)}
                >
                  <span className="section-nav-index">{i + 1}</span>
                  <span className="section-nav-text">
                    <span className="section-nav-label">{s.label}</span>
                    <span className="section-nav-blurb">{s.blurb}</span>
                  </span>
                </button>
              ))}
              <p className="section-nav-hint">Keys 1–8 or ← →</p>
            </nav>

            <section className="panel focus-pane" id="focus-pane">
              <div className="focus-header">
                <h2 id="focus-title">Play</h2>
                <p className="focus-blurb" id="focus-blurb" />
              </div>
              <div id="section-controls" />
              <div className="focus-plots">
                <div className="focus-plot" data-plot="plot-belief" hidden>
                  <div
                    className="chart-caption impact-caption"
                    data-truth-caption="belief"
                  >
                    Belief
                  </div>
                  <D3ChartHost id="chart-belief" className="chart" />
                </div>
                <div className="focus-plot" data-plot="plot-sales-demand" hidden>
                  <div className="chart-caption impact-caption">Sales vs demand</div>
                  <D3ChartHost id="chart-sales-demand" className="chart" />
                </div>
                <div className="focus-plot" data-plot="plot-pnl" hidden>
                  <div className="chart-caption impact-caption">
                    Cumulative revenue · cost · profit
                  </div>
                  <D3ChartHost id="chart-pnl-series" className="chart" />
                </div>
                <div className="focus-plot" data-plot="plot-survival" hidden>
                  <div className="chart-caption impact-caption">Survival + lot rug</div>
                  <D3ChartHost id="chart-survival" className="chart" />
                </div>
                <div className="focus-plot" data-plot="plot-demand" hidden>
                  <div className="chart-caption impact-caption">
                    DOW demand · protection 3 / 3 / 4
                  </div>
                  <D3ChartHost id="chart-demand" className="chart" />
                </div>
                <div className="focus-plot" data-plot="plot-inventory" hidden>
                  <div className="chart-caption impact-caption">
                    Inventory vs base-stock
                  </div>
                  <D3ChartHost id="chart-inventory" className="chart" />
                </div>
                <div className="focus-plot" data-plot="plot-age-comp" hidden>
                  <div className="chart-caption impact-caption">On-hand by age band</div>
                  <D3ChartHost id="chart-age-comp" className="chart" />
                </div>
                <div className="focus-plot" data-plot="plot-arrival-prior" hidden>
                  <div className="chart-caption impact-caption">
                    Arrival-age prior · receipt rug
                  </div>
                  <D3ChartHost id="chart-arrival-prior" className="chart" />
                </div>
                <div className="focus-plot" data-plot="plot-arrival-shift" hidden>
                  <div className="chart-caption impact-caption">
                    Transit ΔT shift vs baseline
                  </div>
                  <D3ChartHost id="chart-arrival-shift" className="chart" />
                </div>
                <div
                  className="focus-plot"
                  data-plot="plot-belief-age-marginal"
                  hidden
                >
                  <div className="chart-caption impact-caption">Age marginal</div>
                  <D3ChartHost id="chart-belief-age-marginal" className="chart" />
                </div>
                <div className="focus-plot" data-plot="plot-belief-lg" hidden>
                  <div
                    className="chart-caption impact-caption"
                    data-truth-caption="belief-lg"
                  >
                    Belief heatmap
                  </div>
                  <D3ChartHost id="chart-belief-lg" className="chart" />
                </div>
                <div className="focus-plot" data-plot="plot-controller-orders" hidden>
                  <div className="chart-caption impact-caption">Order quantity</div>
                  <D3ChartHost id="chart-controller-orders" className="chart" />
                </div>
              </div>
            </section>
          </div>
        </aside>
      </div>

      <div id="studio-error" className="studio-error" hidden role="alert" />
      <footer className="foot" id="studio-footer" />
    </div>
  );
}
