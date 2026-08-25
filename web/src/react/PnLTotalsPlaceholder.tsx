/** Static PnL totals shell — mirrors renderPnLTotals layout with zero values. */
export function PnLTotalsPlaceholder() {
  return (
    <div
      className="pnl-totals pnl-totals--compact"
      data-testid="pnl-totals-placeholder"
    >
      <div className="pnl-totals-line">
        <span className="pnl-item">
          <span className="pnl-label">Revenue</span>
          <span className="pnl-value pnl-value--rev">$0</span>
        </span>
        <span className="pnl-sep" aria-hidden="true">·</span>
        <span className="pnl-item">
          <span className="pnl-label">Cost</span>
          <span className="pnl-value pnl-value--cost">$0</span>
        </span>
        <span className="pnl-sep" aria-hidden="true">·</span>
        <span className="pnl-item pnl-item--emphasis">
          <span className="pnl-label">Profit</span>
          <span className="pnl-value pnl-value--profit is-pos">$0</span>
        </span>
      </div>
      <div className="pnl-totals-line">
        <span className="pnl-item">
          <span className="pnl-label">Missed sales</span>
          <span className="pnl-value pnl-value--missed">0</span>
        </span>
        <span className="pnl-sep" aria-hidden="true">·</span>
        <span className="pnl-item">
          <span className="pnl-label">Waste</span>
          <span className="pnl-value pnl-value--waste">0</span>
        </span>
      </div>
    </div>
  );
}
