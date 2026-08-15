import type { ViewModel } from "../types";

function money(n: number): string {
  const sign = n < 0 ? "−" : "";
  return `${sign}$${Math.abs(n).toFixed(0)}`;
}

export function renderPnLTotals(
  container: HTMLElement,
  vm: ViewModel,
): void {
  const t = vm.pnl_totals;
  container.innerHTML = `
    <div class="pnl-totals">
      <div class="pnl-row">
        <span class="pnl-label">Episode revenue</span>
        <span class="pnl-value pnl-value--rev">${money(t.revenue)}</span>
      </div>
      <div class="pnl-row">
        <span class="pnl-label">Episode cost</span>
        <span class="pnl-value pnl-value--cost">${money(t.cost)}</span>
      </div>
      <div class="pnl-row pnl-row--emphasis">
        <span class="pnl-label">Episode profit</span>
        <span class="pnl-value pnl-value--profit ${t.profit >= 0 ? "is-pos" : "is-neg"}">${money(t.profit)}</span>
      </div>
      <div class="pnl-divider"></div>
      <div class="pnl-today">
        <div class="pnl-today-title">Today (day ${vm.episode_day})</div>
        <div class="pnl-today-grid">
          <div>
            <div class="micro-label">Revenue</div>
            <div class="micro-value">${money(t.today_revenue)}</div>
          </div>
          <div>
            <div class="micro-label">Cost</div>
            <div class="micro-value">${money(t.today_cost)}</div>
          </div>
          <div>
            <div class="micro-label">Profit</div>
            <div class="micro-value ${t.today_profit >= 0 ? "is-pos" : "is-neg"}">${money(t.today_profit)}</div>
          </div>
        </div>
      </div>
    </div>
  `;
}
