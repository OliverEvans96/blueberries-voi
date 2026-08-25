import { D3ChartHost } from "./D3ChartHost";
import { InfoTip } from "./InfoTip";
import { TitleBarBlogLink, TitleBarExternalActions } from "./TitleBarLinks";

const D3_CHART_IDS = [
  "chart-sales",
  "chart-stockout",
  "chart-history",
  "chart-sales-demand",
  "chart-demand",
  "chart-age-comp",
  "chart-arrival-prior",
  "chart-arrival-shift",
  "chart-arrhenius-temp",
  "chart-gamma-path",
  "chart-belief-age-marginal",
  "chart-belief-lg",
  "chart-controller-orders",
  "chart-spoil",
  "chart-age-comp-focus",
  "chart-controller-orders-focus",
  "chart-spoil-focus",
] as const;

/** Static studio shell — Cockpit Grid layout v7 (T-158). */
export function StudioLayout() {
  return (
    <div className="bv-studio">
      <div className="shell studio">
        <header className="title-bar">
          <div className="title-bar-heading">
            <h1>Blueberry inventory studio</h1>
            <TitleBarBlogLink />
          </div>
          <div className="title-bar-actions">
            <TitleBarExternalActions />
            <button
              type="button"
              id="tuning-drawer-trigger"
              className="tuning-drawer-trigger"
              aria-label="Simulation parameters"
              aria-expanded="false"
              aria-controls="tuning-drawer"
            />
            <InfoTip alignEnd>
              Opens the full simulation-parameters tuning dock, with every
              knob for demand, arrival, physics, logistics, and autopilot
              grouped into topic tabs.
            </InfoTip>
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
            <InfoTip alignEnd>
              Shows whether the Rust simulation engine, compiled to
              WebAssembly and running entirely in your browser, has finished
              loading and is ready to advance days.
            </InfoTip>
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
              <span className="heading-with-tip">
                <h2>Outcomes</h2>
                <InfoTip>
                  Turns each simulated day into profit-and-loss, on-hand
                  inventory by freshness band, and order, spoilage, and sales
                  flow — the numbers used to judge whether an ordering policy
                  is actually paying off.
                </InfoTip>
              </span>
              <span className="panel-note">
                Money, stock, and daily flow for this run.
              </span>
            </div>
            <div id="pnl-totals-host" data-testid="pnl-totals-host" />
            <div className="metrics-stack">
              <div className="chart-caption">
                Cumulative revenue · cost · profit
                <InfoTip>
                  Running totals of revenue, cost, and profit across the days
                  simulated so far. Each day's profit is margin earned on
                  units sold, minus waste cost on units spoiled, minus a
                  stockout penalty on demand the shelf couldn't meet — holding
                  unsold inventory overnight costs nothing in this accounting.
                </InfoTip>
              </div>
              <D3ChartHost
                id="chart-pnl-economics"
                className="chart chart-pnl-economics"
                ariaLabel="Cumulative profit and loss"
              />
              <div className="chart-caption impact-caption">
                Sales &amp; demand
                <InfoTip>
                  Units actually sold each day plotted against that day's
                  total demand, which follows a repeating day-of-week rhythm
                  rather than a flat average. The gap between the two lines is
                  a stockout — demand that showed up but couldn't be met
                  because the shelf ran empty first.
                </InfoTip>
              </div>
              <D3ChartHost
                id="chart-sales-demand"
                className="chart"
                ariaLabel="Sales versus demand with stockout gap"
              />
              <div className="chart-caption impact-caption">
                Order quantity
                <InfoTip>
                  Units the controller ordered each simulated day — the
                  policy's refill decision given on-hand stock, demand
                  expectations, and spoilage risk. Spikes usually line up
                  with delivery days or stockout recovery.
                </InfoTip>
              </div>
              <D3ChartHost
                id="chart-controller-orders"
                className="chart"
                ariaLabel="Order quantity over days"
              />
              <div className="chart-caption impact-caption">
                Spoilage
                <InfoTip>
                  Units spoiled each day as individual freshness runs out.
                  Spoilage happens unit by unit, so deliveries can waste
                  across several days rather than all at once — watching
                  this alongside orders shows whether buying is outpacing
                  what the shelf can sell through in time.
                </InfoTip>
              </div>
              <D3ChartHost
                id="chart-spoil"
                className="chart"
                ariaLabel="Daily spoilage over days"
              />
            </div>
          </section>

          <div
            className="cockpit-column cockpit-column--center"
            data-testid="cockpit-center"
          >
            <section
              className="cockpit-pane cockpit-pane--run panel"
              data-testid="cockpit-run"
              aria-label="Run"
            >
              <div id="operator-bar-host" />
            </section>

            <section
              className="cockpit-pane cockpit-pane--belief panel"
              data-testid="cockpit-belief"
              aria-label="Belief"
            >
              <div className="panel-head">
                <span className="heading-with-tip">
                  <h2>Belief</h2>
                  <InfoTip>
                    This column shows what the particle filter currently
                    believes about freshness across the shelf's lots: a crowd of
                    hundreds of complete hypothetical shelf states, weighted by
                    how well each matches the sales, waste, and lot data
                    observed so far. It reflects belief, not the hidden
                    ground-truth freshness state the simulation is actually
                    running underneath.
                  </InfoTip>
                </span>
                <span className="panel-note" id="hover-note">
                  Filter belief over time — hover a day to link charts.
                </span>
              </div>
              <div className="chart-caption" data-truth-caption="lots">
              Freshness × time
              <InfoTip>
                A heatmap of the particle filter's believed freshness
                distribution for each lot over time, with the hidden
                ground-truth freshness the simulation actually tracked
                overlaid for comparison. Freshness runs from 1 (pristine) down
                to 0 (spoiled) and decays at each unit's own pace, not on a
                calendar age shared by everything from the same delivery.
              </InfoTip>
            </div>
            <D3ChartHost
              id="chart-history"
              className="chart"
              ariaLabel="Belief freshness over time with truth overlay"
            />
            <p className="belief-mae-stat" data-belief-mae="history" hidden />
            <div
              className="chart-caption impact-caption"
              data-truth-caption="age-comp"
            >
              On-hand by freshness band
              <InfoTip>
                Groups on-hand units into freshness bands instead of one flat
                count, because a unit close to spoiling barely protects
                against tomorrow's demand the way a pristine one does. The
                controller orders off this freshness-weighted total, called
                effective inventory, rather than a plain unit count.
              </InfoTip>
            </div>
            <D3ChartHost
              id="chart-age-comp"
              className="chart"
              ariaLabel="On-hand inventory by freshness band with effective overlay"
            />
            <div
              className="chart-caption impact-caption"
              data-truth-caption="belief-lg"
            >
              Freshness histogram
              <InfoTip>
                A histogram of the particle filter's current belief over
                freshness values across the shelf's units, built from the bank
                of hypothetical shelf states the filter maintains rather than
                a single number. It can show several separated bumps instead
                of one smooth curve, reflecting genuine uncertainty about
                which units are still fresh and which are close to spoiling.
              </InfoTip>
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
            </section>
          </div>

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
