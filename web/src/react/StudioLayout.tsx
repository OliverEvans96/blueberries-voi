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

/** Static studio shell — Cockpit Grid layout v6 (T-148). */
export function StudioLayout() {
  return (
    <div className="bv-studio">
      <div className="shell studio">
        <header className="title-bar">
          <h1>Blueberry inventory studio</h1>
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
        </header>

        <div
          className="cockpit-grid"
          data-testid="cockpit-grid"
          data-layout="v6"
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
              </div>
              <div className="tuning-dock-body">
                <div className="focus-header">
                  <h2 id="focus-title">Demand</h2>
                  <p className="focus-blurb" id="focus-blurb" />
                </div>
                <div className="tuning-dock-columns">
                  <div id="section-controls" className="tuning-dock-controls" />
                  <div className="focus-plots tuning-plots">
                    <div className="focus-plot" data-plot="plot-demand" hidden>
                      <div className="chart-caption impact-caption">
                        Daily demand
                      </div>
                      <div
                        id="chart-demand-host"
                        className="chart demand-chart-slot"
                        role="img"
                        aria-label="Daily demand over episode days"
                      />
                    </div>
                    <div
                      className="focus-plot"
                      data-plot="plot-demand-forecast"
                      hidden
                    >
                      <div className="chart-caption impact-caption">
                        Demand forecast
                      </div>
                      <div
                        id="chart-demand-forecast-host"
                        className="chart demand-chart-slot"
                        role="img"
                        aria-label="Known demand distribution for the next few days"
                      />
                    </div>
                    <div
                      className="focus-plot"
                      data-plot="plot-picking-variability"
                      hidden
                    >
                      <div className="chart-caption impact-caption">
                        Picking variability shape
                      </div>
                      <div
                        id="picking-var-chart"
                        className="chart picking-var-chart"
                        role="img"
                        aria-label="Picking weight curve"
                      />
                    </div>
                    <div
                      className="focus-plot"
                      data-plot="plot-logistics-calendar"
                      hidden
                    >
                      <div className="field week-calendar-field">
                        <span className="field-label">Delivery schedule</span>
                        <div
                          id="week-calendar"
                          className="week-calendar"
                          role="group"
                          aria-label="Delivery and order weekdays"
                        />
                        <div
                          className="week-calendar-legend"
                          role="note"
                          aria-label="Calendar legend"
                        >
                          <span className="week-calendar-legend-item">
                            <span
                              className="week-calendar-swatch is-delivery"
                              aria-hidden="true"
                            />
                            Delivery day
                          </span>
                          <span className="week-calendar-legend-item">
                            <span
                              className="week-calendar-swatch is-order"
                              aria-hidden="true"
                            />
                            Order day
                          </span>
                          <span className="week-calendar-legend-item">
                            <span
                              className="week-calendar-swatch is-both"
                              aria-hidden="true"
                            />
                            Both
                          </span>
                        </div>
                        <p
                          className="meta-readonly week-calendar-hint"
                          id="week-calendar-hint"
                          hidden
                        >
                          Reset to apply schedule
                        </p>
                      </div>
                    </div>
                    <div className="focus-plot" data-plot="plot-inventory" hidden>
                      <div className="chart-caption impact-caption">
                        Effective inventory preview
                      </div>
                      <D3ChartHost
                        id="chart-inventory-focus"
                        className="chart"
                        ariaLabel="Inventory versus base stock target preview"
                      />
                    </div>
                    <div
                      className="focus-plot"
                      data-plot="plot-controller-orders"
                      hidden
                    >
                      <div className="chart-caption impact-caption">
                        Order quantity
                      </div>
                      <D3ChartHost
                        id="chart-controller-orders-focus"
                        className="chart"
                        ariaLabel="Order quantity preview"
                      />
                    </div>
                    <div className="focus-plot" data-plot="plot-spoil" hidden>
                      <div className="chart-caption impact-caption">Spoilage</div>
                      <D3ChartHost
                        id="chart-spoil-focus"
                        className="chart"
                        ariaLabel="Spoilage preview"
                      />
                    </div>
                    <div className="focus-plot" data-plot="plot-arrival-prior" hidden>
                      <div className="chart-caption impact-caption">
                        Arrival freshness prior · receipt rug
                      </div>
                      <D3ChartHost
                        id="chart-arrival-prior"
                        className="chart"
                        ariaLabel="Arrival freshness prior distribution"
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
            </div>
          </section>
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
        <div id="day-inspector-host" data-testid="day-inspector-host" />
      </div>
    </div>
  );
}

export { D3_CHART_IDS };
