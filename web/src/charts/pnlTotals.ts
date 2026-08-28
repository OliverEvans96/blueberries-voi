import { computeImpactTotals } from "../metrics/impactTotals";
import type { ViewModel } from "../types";

function money(n: number): string {
  const sign = n < 0 ? "−" : "";
  return `${sign}$${Math.abs(n).toFixed(0)}`;
}

function units(n: number): string {
  return n.toFixed(0);
}

function pct(n: number): string {
  return `${n.toFixed(0)}%`;
}

export function renderPnLTotals(
  container: HTMLElement,
  vm: ViewModel,
): void {
  // Episode totals for the full horizon (not a rolling window).
  const t = vm.pnl_totals;
  const impact = computeImpactTotals(vm.history);
  const serviceLevelPct = (1 - impact.missedPct) * 100;
  const wastePct = impact.wastePct * 100;
  container.innerHTML = `
    <div class="pnl-totals pnl-totals--compact">
      <div class="pnl-totals-line">
        <span class="pnl-item">
          <span class="pnl-label">Revenue</span>
          <span class="pnl-value pnl-value--rev">${money(t.revenue)}</span>
        </span>
        <span class="pnl-sep" aria-hidden="true">·</span>
        <span class="pnl-item">
          <span class="pnl-label">Cost</span>
          <span class="pnl-value pnl-value--cost">${money(t.cost)}</span>
        </span>
        <span class="pnl-sep" aria-hidden="true">·</span>
        <span class="pnl-item pnl-item--emphasis">
          <span class="pnl-label">Profit</span>
          <span class="pnl-value pnl-value--profit ${t.profit >= 0 ? "is-pos" : "is-neg"}">${money(t.profit)}</span>
        </span>
      </div>
      <div class="pnl-totals-line">
        <span class="pnl-item">
          <span class="pnl-label">Service level</span>
          <span class="pnl-value pnl-value--service">${pct(serviceLevelPct)} (${units(impact.missedTotal)} missed sales)</span>
        </span>
        <span class="pnl-sep" aria-hidden="true">·</span>
        <span class="pnl-item">
          <span class="pnl-label">Food waste</span>
          <span class="pnl-value pnl-value--waste">${pct(wastePct)} (${units(impact.wasteTotal)} units)</span>
        </span>
      </div>
    </div>
  `;
}
