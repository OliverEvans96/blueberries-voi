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
    <div class="pnl-totals pnl-totals--compact">
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
    </div>
  `;
}
