/**
 * Economics pane — P&L summary + cumulative chart + pricing hosts (T-127 AC-layout).
 */
import { renderPnLTimeseries } from "../charts/pnlTimeseries";
import type { DayPnL, ViewModel } from "../types";

export type EconomicsPaneProps = {
  vm: ViewModel;
  onPricingChange?: (field: string, value: number) => void;
};

/** Self-contained D3 mount for cumulative revenue / cost / profit (Economics pane). */
export function mountEconomicsPnLChart(
  container: HTMLElement,
  series: DayPnL[],
  height = 160,
): void {
  renderPnLTimeseries(container, series, height);
}

export function EconomicsPane({ vm }: EconomicsPaneProps) {
  const pnl = vm.pnl_totals;
  return (
    <section className="economics-pane panel" data-pane="economics" aria-label="Economics">
      <div className="panel-head">
        <h2>Economics</h2>
      </div>
      <div id="chart-pnl-totals" className="pnl-summary" data-testid="pnl-consolidated">
        <div>Revenue: {pnl?.revenue ?? 0}</div>
        <div>Cost: {pnl?.cost ?? 0}</div>
        <div>Profit: {pnl?.profit ?? 0}</div>
      </div>
      <div className="economics-chart-block">
        <div className="chart-caption">Cumulative revenue · cost · profit</div>
        <div
          id="chart-pnl-economics"
          className="chart chart-pnl-economics"
          data-testid="chart-pnl-economics"
          ref={(node) => {
            if (node) mountEconomicsPnLChart(node, vm.pnl_series);
          }}
        />
      </div>
      <div id="economics-pricing-host" className="economics-pricing-host" />
    </section>
  );
}
