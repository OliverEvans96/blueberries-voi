import { useState } from "react";
import { D3ChartHost } from "./D3ChartHost";
import { HostHoverTip } from "./HostHoverTip";
import { InfoTip } from "./InfoTip";
import { TitleBarBlogLink, TitleBarExternalActions } from "./TitleBarLinks";
import { WelcomeModal } from "./WelcomeModal";

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
  const [welcomeOpen, setWelcomeOpen] = useState(true);

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
            <HostHoverTip
              alignEnd
              tip="Opens the full tuning dock, with every parameter grouped into topic tabs."
            >
              <button
                type="button"
                id="tuning-drawer-trigger"
                className="tuning-drawer-trigger"
                aria-label="Simulation parameters"
                aria-expanded="false"
                aria-controls="tuning-drawer"
              />
            </HostHoverTip>
            <HostHoverTip
              alignEnd
              tip="Shows whether the simulation engine has finished loading and is ready to advance days."
            >
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
            </HostHoverTip>
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
                  The numbers used to judge whether an ordering policy is
                  paying off: profit and loss, on-hand inventory, and daily
                  order, spoilage, and sales flow.
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
                  Running totals of revenue, cost, and profit. Each day's
                  profit is margin on units sold, minus waste cost on units
                  spoiled, minus a stockout penalty on unmet demand.
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
                  Units sold each day versus that day's total demand. The gap
                  between the lines is a stockout — demand the empty shelf
                  couldn't meet.
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
                  Units the controller ordered each day, given on-hand stock,
                  demand, and spoilage risk. Spikes usually line up with
                  delivery days or stockout recovery.
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
                  Units spoiled each day. Watching this alongside orders shows
                  whether buying is outpacing what the shelf can sell through
                  in time.
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
                    What the particle filter currently believes about
                    freshness across the shelf's lots, based on sales, waste,
                    and lot data observed so far. This is belief, not the
                    hidden ground truth running underneath.
                  </InfoTip>
                </span>
                <span className="panel-note" id="hover-note">
                  Filter belief over time — hover a day to link charts.
                </span>
              </div>
              <div className="chart-caption" data-truth-caption="lots">
              <span data-truth-caption-label>
                Historical Freshness Distribution
              </span>
              <InfoTip>
                A heatmap of believed freshness per lot over time, with the
                hidden ground truth overlaid for comparison. Freshness runs
                from 1 (pristine) to 0 (spoiled) and decays at each unit's own
                pace.
              </InfoTip>
            </div>
            <D3ChartHost
              id="chart-history"
              className="chart"
              ariaLabel="Belief freshness over time with truth overlay"
            />
            <div
              className="chart-caption impact-caption"
              data-truth-caption="age-comp"
            >
              <span data-truth-caption-label>
                Historical Freshness Summary
              </span>
              <InfoTip>
                Groups on-hand units into freshness bands, since a unit close
                to spoiling barely protects against tomorrow's demand. The
                controller orders off this freshness-weighted total, called
                effective inventory.
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
              <span data-truth-caption-label>
                Today&apos;s Freshness Distribution
              </span>
              <InfoTip>
                A histogram of the filter's current belief over freshness
                values. Separate bumps instead of one smooth curve reflect
                genuine uncertainty about which units are close to spoiling.
              </InfoTip>
            </div>
            <D3ChartHost
              id="chart-belief-lg"
              className="chart"
              ariaLabel="Today's Freshness Distribution"
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
            <table
              className="belief-mae-table"
              data-belief-mae-table
              hidden
            >
              <caption>Belief accuracy (Omniscience)</caption>
              <thead>
                <tr>
                  <th scope="col" />
                  <th scope="col">Mean</th>
                  <th scope="col">Distribution</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th scope="row">Today</th>
                  <td data-belief-mae-today-mean />
                  <td data-belief-mae-today-dist />
                </tr>
                <tr>
                  <th scope="row">All days</th>
                  <td data-belief-mae-all-mean />
                  <td data-belief-mae-all-dist />
                </tr>
              </tbody>
            </table>
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
      <WelcomeModal
        open={welcomeOpen}
        onDismiss={() => setWelcomeOpen(false)}
      />
    </div>
  );
}

export { D3_CHART_IDS };
