import { useRef } from "react";
import { D3ChartHost } from "./D3ChartHost";
import { ReferenceDrawer } from "./ReferenceDrawer";

const D3_CHART_IDS = [
  "chart-sales",
  "chart-stockout",
  "chart-history",
  "chart-spoil",
  "chart-sales-demand",
  "chart-demand",
  "chart-inventory",
  "chart-age-comp",
  "chart-arrival-prior",
  "chart-arrival-shift",
  "chart-arrhenius-temp",
  "chart-gamma-path",
  "chart-belief-age-marginal",
  "chart-belief-lg",
  "chart-controller-orders",
] as const;

/** Static studio shell — Cockpit Grid layout v5 (T-128). */
export function StudioLayout() {
  const portalRef = useRef<HTMLDivElement>(null);

  return (
    <div className="bv-studio">
    <div className="shell studio">
      <header className="hero">
        <div className="hero-top">
          <div className="brand">Cold Case Ledger</div>
          <div className="hero-tools">
            <div id="guided-paths-host" className="guided-paths-host" />
            <ReferenceDrawer portalContainerRef={portalRef} />
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
        </div>
        <h1>Blueberry inventory studio</h1>
        <p className="lede">
          Always-on cockpit: freshness belief, economics, events, and run controls
          with a tuning dock for deeper teaching plots.
        </p>
        <div id="insight-strip-host" className="insight-strip-host" />
        <div id="chapter-tabs-host" className="chapter-tabs-host" />
      </header>

      <div className="cockpit-grid" data-testid="cockpit-grid" data-layout="v5">
        <section
          className="cockpit-row cockpit-row--charts"
          data-testid="cockpit-row-charts"
          id="linked-charts"
        >
          <div className="cockpit-pane cockpit-pane--primary panel">
            <div className="panel-head">
              <h2>Primary</h2>
              <span className="panel-note" id="hover-note">
                Hover a day to highlight it everywhere
              </span>
            </div>
            <div className="legend-inline store-legend">
              <span className="chip chip-sales">Sales</span>
              <span className="chip chip-lots">Units (trajectories)</span>
              <span className="chip chip-spoil">Spoilage</span>
              <span className="chip chip-missed">Missed</span>
            </div>
            <div className="chart-stack primary-charts">
              <div className="chart-caption" data-truth-caption="lots">
                Freshness × time
              </div>
              <D3ChartHost
                id="chart-history"
                className="chart"
                ariaLabel="Belief freshness over time with truth overlay"
              />
              <div className="chart-caption impact-caption">Sales vs demand</div>
              <D3ChartHost
                id="chart-sales-demand"
                className="chart"
                ariaLabel="Sales versus demand with stockout gap"
              />
              <div className="chart-caption">Units spoiled</div>
              <D3ChartHost
                id="chart-spoil"
                className="chart"
                ariaLabel="Units spoiled by day"
              />
            </div>
          </div>

          <div className="cockpit-pane cockpit-pane--secondary panel">
            <div className="panel-head">
              <h2>Secondary</h2>
            </div>
            <div
              className="chart-caption impact-caption"
              data-truth-caption="belief-lg"
            >
              Freshness histogram
            </div>
            <D3ChartHost
              id="chart-belief-lg"
              className="chart"
              ariaLabel="Freshness histogram"
            />
            <div className="chart-caption impact-caption" hidden>
              Age marginal
            </div>
            <div
              id="chart-belief-age-marginal"
              className="chart"
              role="img"
              aria-label="Belief age marginal"
              hidden
            />
            <div id="secondary-chrome-host" className="secondary-chrome-host" />
            <div id="operator-bar-host" />
          </div>
        </section>

        <div
          id="economics-pane-host"
          className="cockpit-pane cockpit-pane--economics"
        />

        <section
          className="cockpit-pane cockpit-pane--today panel"
          data-testid="cockpit-today"
          aria-label="Today strip"
        >
          <h3 className="run-today-heading">Today</h3>
          <div className="run-today-charts">
            <div className="run-today-cell">
              <div className="chart-caption impact-caption">
                Inventory vs base-stock
              </div>
              <D3ChartHost
                id="chart-inventory"
                className="chart chart--compact"
                ariaLabel="Inventory versus base stock target"
              />
            </div>
            <div className="run-today-cell">
              <div className="chart-caption impact-caption">Order quantity</div>
              <D3ChartHost
                id="chart-controller-orders"
                className="chart chart--compact"
                ariaLabel="Controller order quantities"
              />
            </div>
            <div className="run-today-cell">
              <div className="chart-caption impact-caption">On-hand by age band</div>
              <D3ChartHost
                id="chart-age-comp"
                className="chart chart--compact"
                ariaLabel="On-hand inventory by age band"
              />
            </div>
          </div>
          <div className="visually-hidden" aria-hidden="true">
            <D3ChartHost
              id="chart-sales"
              className="chart chart--compact"
              ariaLabel="Units sold by day"
            />
            <D3ChartHost
              id="chart-stockout"
              className="chart chart--compact"
              ariaLabel="Missed sales by day"
            />
            <D3ChartHost
              id="chart-demand"
              className="chart"
              ariaLabel="Day of week demand profile"
            />
          </div>
        </section>

        <div
          id="events-pane-host"
          className="cockpit-pane cockpit-pane--events"
          data-testid="cockpit-events-column"
        />

        <section
          className="cockpit-row cockpit-row--tuning"
          data-testid="cockpit-row-tuning"
        >
          <div className="tuning-dock panel">
            <div
              className="tuning-dock-tabs"
              role="tablist"
              aria-label="Tuning clusters"
            >
              <div className="tuning-cluster" role="presentation">
                <span className="tuning-cluster-label">Sim params</span>
                <div className="tuning-cluster-tabs">
                  <button
                    type="button"
                    role="tab"
                    data-section="demand"
                    aria-controls="section-controls"
                  >
                    Demand
                  </button>
                  <button
                    type="button"
                    role="tab"
                    data-section="observation"
                    aria-controls="section-controls"
                  >
                    Observation
                  </button>
                  <button
                    type="button"
                    role="tab"
                    data-section="arrival"
                    aria-controls="section-controls"
                  >
                    Arrival
                  </button>
                  <button
                    type="button"
                    role="tab"
                    data-section="physics"
                    aria-controls="section-controls"
                  >
                    Physics
                  </button>
                </div>
              </div>
              <div className="tuning-cluster" role="presentation">
                <span className="tuning-cluster-label">Logistics</span>
                <div className="tuning-cluster-tabs">
                  <button
                    type="button"
                    role="tab"
                    data-section="logistics"
                    aria-controls="section-controls"
                  >
                    Logistics
                  </button>
                </div>
              </div>
              <div className="tuning-cluster" role="presentation">
                <span className="tuning-cluster-label">Autopilot</span>
                <div className="tuning-cluster-tabs">
                  <button
                    type="button"
                    role="tab"
                    data-section="autopilot"
                    aria-controls="section-controls"
                  >
                    Autopilot
                  </button>
                </div>
              </div>
              <button
                type="button"
                className="tuning-future-chip"
                disabled
                aria-disabled="true"
              >
                Future
              </button>
            </div>
            <div className="tuning-dock-body">
              <div className="focus-header">
                <h2 id="focus-title">Demand</h2>
                <p className="focus-blurb" id="focus-blurb" />
              </div>
              <div id="section-controls" />
              <div className="focus-plots tuning-plots">
                <div className="focus-plot" data-plot="plot-arrival-prior" hidden>
                  <div className="chart-caption impact-caption">
                    Arrival-age prior · receipt rug
                  </div>
                  <D3ChartHost
                    id="chart-arrival-prior"
                    className="chart"
                    ariaLabel="Arrival age prior distribution"
                  />
                </div>
                <div className="focus-plot" data-plot="plot-arrival-shift" hidden>
                  <div className="chart-caption impact-caption">
                    Transit ΔT shift vs baseline
                  </div>
                  <D3ChartHost
                    id="chart-arrival-shift"
                    className="chart"
                    ariaLabel="Transit temperature shift"
                  />
                </div>
                <div className="focus-plot" data-plot="plot-arrhenius-temp" hidden>
                  <div className="chart-caption impact-caption">
                    Q10 aging rate vs temperature
                  </div>
                  <D3ChartHost
                    id="chart-arrhenius-temp"
                    className="chart"
                    ariaLabel="Q10 aging rate versus store temperature"
                  />
                </div>
                <div className="focus-plot" data-plot="plot-gamma-path" hidden>
                  <div className="chart-caption impact-caption">
                    Gamma freshness mean ± σ until expiry
                  </div>
                  <D3ChartHost
                    id="chart-gamma-path"
                    className="chart"
                    ariaLabel="Unit freshness mean and standard deviation envelope"
                  />
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>

      <div id="studio-error" className="studio-error" hidden role="alert" />
      <footer className="foot" id="studio-footer" />
      {/* Preserve chart id enumeration for layout tests */}
      <span id="d3-chart-id-registry" hidden>
        {D3_CHART_IDS.join(",")}
      </span>
    </div>
    <div
      ref={portalRef}
      className="bv-studio-portal-root"
      data-studio-portal=""
      aria-hidden="true"
    >
      <div id="studio-loading-host" data-testid="studio-loading-host" />
    </div>
    </div>
  );
}

export { D3_CHART_IDS };
