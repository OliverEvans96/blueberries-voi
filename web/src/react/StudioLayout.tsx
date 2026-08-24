import { D3ChartHost } from "./D3ChartHost";

const D3_CHART_IDS = [
  "chart-sales",
  "chart-stockout",
  "chart-history",
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
  "chart-spoil",
  "chart-inventory-focus",
  "chart-controller-orders-focus",
  "chart-spoil-focus",
] as const;

/** Static studio shell — Cockpit Grid layout v7 (T-158). */
export function StudioLayout() {
  return (
    <div className="bv-studio">
      <div className="shell studio">
        <header className="title-bar">
          <h1>Blueberry inventory studio</h1>
          <div className="title-bar-actions">
            <button
              type="button"
              id="tuning-drawer-trigger"
              className="tuning-drawer-trigger"
              aria-label="Simulation parameters"
              aria-expanded="false"
              aria-controls="tuning-drawer"
            />
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
        </header>

        <div
          className="cockpit-grid"
          data-testid="cockpit-grid"
          data-layout="v7"
          id="linked-charts"
        >
          <section
            className="cockpit-pane cockpit-pane--metrics panel"
            data-testid="cockpit-metrics"
            aria-label="Metrics"
          >
            <div className="panel-head">
              <h2>Outcomes</h2>
              <span className="panel-note">
                Money, stock, and daily flow for this run.
              </span>
            </div>
            <div id="pnl-totals-host" data-testid="pnl-totals-host" />
            <div className="impact-row">
              <div id="impact-missed-host" data-testid="impact-missed-host" />
              <div id="impact-waste-host" data-testid="impact-waste-host" />
            </div>
            <div className="metrics-stack">
              <div className="metrics-group metrics-group--economics">
                <div className="metrics-group-label">Economics</div>
                <div className="chart-caption">Cumulative revenue · cost · profit</div>
                <D3ChartHost
                  id="chart-pnl-economics"
                  className="chart chart-pnl-economics"
                  ariaLabel="Cumulative profit and loss"
                />
              </div>
              <div className="metrics-group metrics-group--inventory">
                <div className="metrics-group-label">Inventory</div>
                <div className="chart-caption impact-caption">
                  On-hand by freshness band
                </div>
                <D3ChartHost
                  id="chart-age-comp"
                  className="chart"
                  ariaLabel="On-hand inventory by freshness band"
                />
                <div className="chart-caption impact-caption">
                  Effective inventory
                </div>
                <D3ChartHost
                  id="chart-inventory"
                  className="chart"
                  ariaLabel="Inventory versus base stock target"
                />
              </div>
              <div className="metrics-group metrics-group--flow">
                <div className="metrics-group-label">Flow</div>
                <div className="chart-caption impact-caption">Order quantity</div>
                <D3ChartHost
                  id="chart-controller-orders"
                  className="chart"
                  ariaLabel="Order quantity over days"
                />
                <div className="chart-caption impact-caption">Spoilage</div>
                <D3ChartHost
                  id="chart-spoil"
                  className="chart"
                  ariaLabel="Daily spoilage over days"
                />
                <div className="chart-caption impact-caption">Sales &amp; demand</div>
                <D3ChartHost
                  id="chart-sales-demand"
                  className="chart"
                  ariaLabel="Sales versus demand with stockout gap"
                />
              </div>
            </div>
          </section>

          <section
            className="cockpit-pane cockpit-pane--belief panel"
            data-testid="cockpit-belief"
            aria-label="Belief"
          >
            <div className="panel-head">
              <h2>Belief</h2>
              <span className="panel-note" id="hover-note">
                Filter belief over time — hover a day to link charts.
              </span>
            </div>
            <div className="chart-caption" data-truth-caption="lots">
              Freshness × time
            </div>
            <D3ChartHost
              id="chart-history"
              className="chart"
              ariaLabel="Belief freshness over time with truth overlay"
            />
            <p className="belief-mae-stat" data-belief-mae="history" hidden />
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
            <p className="belief-mae-stat" data-belief-mae="histogram" hidden />
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
            <div className="chart-caption impact-caption">
              Controller tradeoff
            </div>
            <div
              className="belief-tradeoff-panel"
              data-testid="belief-tradeoff-panel"
            >
              <div
                className="tuning-cluster-tabs belief-tradeoff-tabs"
                role="tablist"
                aria-label="Tradeoff view"
              >
                <button
                  type="button"
                  role="tab"
                  data-tradeoff-tab="curve"
                  aria-selected="true"
                  aria-controls="tradeoff-curve-host"
                >
                  Curve
                </button>
                <button
                  type="button"
                  role="tab"
                  data-tradeoff-tab="histogram"
                  aria-selected="false"
                  aria-controls="tradeoff-histogram-host"
                >
                  Histogram
                </button>
              </div>
              <div
                id="tradeoff-curve-host"
                className="tradeoff-chart-host tradeoff-curve chart"
                data-testid="tradeoff-curve"
                role="img"
                aria-label="Tradeoff curve"
              />
              <div
                id="tradeoff-histogram-host"
                className="tradeoff-chart-host tradeoff-histogram chart"
                data-testid="tradeoff-histogram"
                role="img"
                aria-label="Tradeoff joint histogram"
                hidden
              />
            </div>
            <div id="operator-bar-host" />
          </section>

          <div
            className="cockpit-pane cockpit-pane--sidebar"
            data-testid="cockpit-sidebar"
          >
            <div id="obs-controls-pane-host" data-testid="obs-controls-host" />
            <div
              id="events-pane-host"
              className="cockpit-pane--events"
              data-testid="cockpit-events-column"
            />
          </div>
        </div>

        <div id="studio-error" className="studio-error" hidden role="alert" />
        <footer className="foot" id="studio-footer" />
        <span id="d3-chart-id-registry" hidden>
          {D3_CHART_IDS.join(",")}
        </span>
        <div className="visually-hidden" aria-hidden="true">
          <D3ChartHost
            id="chart-sales"
            className="chart"
            ariaLabel="Units sold by day"
          />
          <D3ChartHost
            id="chart-stockout"
            className="chart"
            ariaLabel="Missed sales by day"
          />
          <D3ChartHost
            id="chart-demand"
            className="chart"
            ariaLabel="Day of week demand profile"
          />
        </div>
      </div>
      <div
        className="bv-studio-portal-root"
        data-studio-portal=""
        aria-hidden="true"
      >
        <div id="studio-loading-host" data-testid="studio-loading-host" />
        <div id="reference-drawer-host" data-testid="reference-drawer-host" />
        <div id="tuning-drawer-host" data-testid="tuning-drawer-host" />
        <div id="day-inspector-host" data-testid="day-inspector-host" />
      </div>
    </div>
  );
}

export { D3_CHART_IDS };
