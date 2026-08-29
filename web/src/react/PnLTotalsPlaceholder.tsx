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
          <span className="pnl-label">Service level</span>
          <span className="pnl-value pnl-value--service">
            <span className="pnl-value-pct">100%</span>
            <span className="pnl-value-detail"> (0 missed sales)</span>
          </span>
        </span>
        <span className="pnl-sep" aria-hidden="true">·</span>
        <span className="pnl-item">
          <span className="pnl-label">Food waste</span>
          <span className="pnl-value pnl-value--waste">
            <span className="pnl-value-pct">0%</span>
            <span className="pnl-value-detail"> (0 units)</span>
          </span>
        </span>
      </div>
    </div>
  );
}
