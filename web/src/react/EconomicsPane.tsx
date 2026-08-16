/**
 * Economics pane — P&L summary + pricing hosts (T-127 AC-layout).
 */
import type { ViewModel } from "../types";

export type EconomicsPaneProps = {
  vm: ViewModel;
  onPricingChange?: (field: string, value: number) => void;
};

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
      <div id="economics-pricing-host" className="economics-pricing-host" />
    </section>
  );
}
