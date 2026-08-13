import type { GhostDeltas } from "../types";

function fmtDelta(n: number, kind: "rate" | "count" | "money"): string {
  const sign = n > 0 ? "+" : n < 0 ? "−" : "";
  const abs = Math.abs(n);
  if (kind === "money") return `${sign}$${abs.toFixed(0)}`;
  if (kind === "rate") return `${sign}${abs.toFixed(2)}/d`;
  return `${sign}${abs.toFixed(0)}`;
}

/** Small KPI strip vs last Reset ghost episode. */
export function renderGhostDeltas(
  container: HTMLElement,
  deltas: GhostDeltas | null,
): void {
  if (!deltas) {
    container.innerHTML = `
      <div class="ghost-deltas ghost-deltas--empty">
        No prior episode yet — hit <strong>Reset episode</strong> to compare.
      </div>
    `;
    return;
  }

  const cls = (n: number, invert = false) => {
    const good = invert ? n <= 0 : n >= 0;
    if (Math.abs(n) < 1e-9) return "";
    return good ? "is-pos" : "is-neg";
  };

  container.innerHTML = `
    <div class="ghost-deltas">
      <div class="ghost-deltas-title">Δ vs last reset</div>
      <div class="ghost-deltas-grid">
        <div>
          <div class="micro-label">Waste rate</div>
          <div class="micro-value ${cls(deltas.waste_rate, true)}">${fmtDelta(deltas.waste_rate, "rate")}</div>
        </div>
        <div>
          <div class="micro-label">Stockouts</div>
          <div class="micro-value ${cls(deltas.stockouts, true)}">${fmtDelta(deltas.stockouts, "count")}</div>
        </div>
        <div>
          <div class="micro-label">Cum profit</div>
          <div class="micro-value ${cls(deltas.profit_cum)}">${fmtDelta(deltas.profit_cum, "money")}</div>
        </div>
      </div>
    </div>
  `;
}
